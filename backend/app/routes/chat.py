from collections import defaultdict, deque
from datetime import datetime
import re
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from openai import APITimeoutError, OpenAI
from ..config import settings
from ..services.attachment_storage import delete_attachment_blob, read_attachment_bytes, store_attachment_bytes
from ..services.attachment_tokens import create_download_token
from ..services.attachment_utils import extract_text_preview
from ..services.image_generation import enforce_generation_rate_limit, generate_image_with_gemini, validate_prompt
from ..services.rag_indexing import get_selected_attachment_chunks, get_user_chunk_debug, index_attachment_chunks, retrieve_relevant_chunks
from ..services.database_chat import try_database_chat_answer

# Try to import database components
try:
    from sqlalchemy.ext.asyncio import AsyncSession
    from ..database import get_db
    from ..models import User, ChatMessage, Attachment, ImageGeneration
    from ..auth import get_current_user
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

router = APIRouter()

MEMORY_CONVERSATION_LIMIT = 5
MEMORY_MESSAGE_LIMIT = MEMORY_CONVERSATION_LIMIT * 2
LLM_TIMEOUT_SECONDS = 60.0

# In-memory fallback storage for non-database mode.
_fallback_session_memory: dict[str, deque[dict[str, str]]] = defaultdict(
    lambda: deque(maxlen=MEMORY_MESSAGE_LIMIT)
)
_user_session_memory: dict[str, deque[dict[str, str]]] = defaultdict(
    lambda: deque(maxlen=MEMORY_MESSAGE_LIMIT)
)

class ChatAttachmentPayload(BaseModel):
    upload_id: int | None = None
    name: str
    mime_type: str
    size: int
    category: str
    text_content: str | None = None


class ChatRequest(BaseModel):
    message: str
    thread_id: int | None = None  # Optional thread ID for grouping conversations
    attachments: list[ChatAttachmentPayload] = []
    mode: Literal["normal", "rag", "db"] = "normal"
    rag_attachment_ids: list[int] = []
    reset_history: bool = False

class ChatResponse(BaseModel):
    answer: str


def _build_rag_context(chunks: list[dict]) -> str | None:
    if not chunks:
        return None

    lines = ["Retrieved knowledge snippets for this user query:"]
    for index, chunk in enumerate(chunks, start=1):
        source = chunk.get("source_name") or "unknown"
        chunk_index = chunk.get("chunk_index")
        distance = chunk.get("distance")
        header = f"{index}. Source={source}"
        if chunk_index is not None:
            header += f", chunk={chunk_index}"
        if distance is not None:
            try:
                header += f", distance={float(distance):.4f}"
            except Exception:
                pass
        lines.append(header)
        lines.append(str(chunk.get("text") or "")[:1400])

    return "\n".join(lines)


def _strip_mode_metadata(text: str) -> str:
    """Remove previously injected mode/chunk/source lines from model output."""
    if not text:
        return ""

    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            cleaned_lines.append(raw_line)
            continue

        if line.startswith("[Normal mode]"):
            continue
        if line.startswith("[RAG mode"):
            continue
        if line.startswith("Sources:"):
            continue

        cleaned_lines.append(raw_line)

    return "\n".join(cleaned_lines).strip()


def _filter_context_messages_for_mode(messages: list[dict[str, str]], mode: str) -> list[dict[str, str]]:
    """Keep mode-specific context isolated so Normal mode cannot consume RAG answers."""
    if mode in {"normal", "db"}:
        filtered: list[dict[str, str]] = []
        for message in messages:
            role = str(message.get("role") or "")
            content = str(message.get("content") or "")
            if role == "assistant" and content.lstrip().startswith("[RAG mode"):
                continue
            filtered.append(message)
        return filtered

    return messages


class ImageGenerationRequest(BaseModel):
    prompt: str
    thread_id: int | None = None


class ImageGenerationAttachmentResponse(BaseModel):
    id: int
    name: str
    mime_type: str
    category: str
    size: int
    download_url: str
    data_url: str | None = None


class ImageGenerationResponse(BaseModel):
    answer: str
    prompt: str
    thread_id: int | None = None
    generation_id: int
    status: str
    image: ImageGenerationAttachmentResponse


def _build_sidebar_items(messages):
    items = []
    for index, message in enumerate(messages):
        if message.role != "user":
            continue

        assistant_preview = None
        if index + 1 < len(messages) and messages[index + 1].role == "assistant":
            assistant_preview = messages[index + 1].content

        items.append(
            {
                "id": message.id,
                "title": message.content[:80],
                "user_message": message.content,
                "assistant_preview": assistant_preview,
                "created_at": message.created_at.isoformat(),
            }
        )

    return list(reversed(items))


def _extract_session_key(request: Request) -> str:
    session_id = request.headers.get("X-Session-Id")
    if session_id:
        return f"session:{session_id}"

    authorization = request.headers.get("Authorization")
    if authorization:
        return f"auth:{authorization}"

    client_host = request.client.host if request.client else "anonymous"
    return f"ip:{client_host}"


def _extract_assistant_text(response) -> str:
    """Normalize model responses into a non-empty assistant text."""
    try:
        message = response.choices[0].message
    except Exception:
        return "I could not generate a response. Please try again."

    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content

    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
                parts.append(str(part["text"]))
        joined = "\n".join(parts).strip()
        if joined:
            return joined

    refusal = getattr(message, "refusal", None)
    if isinstance(refusal, str) and refusal.strip():
        return refusal

    return "I could not generate a text response. Please try again."


def _build_recent_questions_context(messages: list[dict[str, str]]) -> str:
    """Build a compact memory hint from recent user questions."""
    user_questions = [m["content"] for m in messages if m.get("role") == "user"][-MEMORY_CONVERSATION_LIMIT:]
    if not user_questions:
        return "No previous user questions are available in the current thread yet."

    lines = [f"{idx}. {question}" for idx, question in enumerate(user_questions, start=1)]
    return "Recent user questions in this thread (oldest to newest):\n" + "\n".join(lines)


def _build_attachment_context(attachments: list[ChatAttachmentPayload]) -> str | None:
    if not attachments:
        return None

    lines: list[str] = ["Attachments included with current request:"]
    for idx, item in enumerate(attachments, start=1):
        base = f"{idx}. {item.name} ({item.category}, {item.mime_type}, {item.size} bytes)"
        if item.text_content:
            lines.append(base + "\nPreview:\n" + item.text_content[:1200])
        else:
            lines.append(base)
    return "\n".join(lines)


def _serialize_attachment(item: Attachment) -> dict:
    token = create_download_token(
        attachment_id=item.id,
        user_id=item.user_id,
        secret_key=settings.secret_key,
        ttl_minutes=settings.attachment_download_token_expire_minutes,
    )
    return {
        "id": item.id,
        "name": item.original_name,
        "mime_type": item.mime_type,
        "category": item.category,
        "size": item.file_size,
        "text_content": item.text_content,
        "download_url": f"/api/uploads/{item.id}/download?token={token}",
    }


def _extension_for_mime(mime_type: str) -> str:
    lower = (mime_type or "").lower()
    if lower == "image/png":
        return "png"
    if lower in {"image/jpeg", "image/jpg"}:
        return "jpg"
    if lower == "image/webp":
        return "webp"
    return "png"


def _is_image_generation_enabled() -> tuple[bool, str | None]:
    api_key = settings.gemini_api_key or settings.litellm_api_key
    if not api_key:
        return False, "Set GEMINI_API_KEY (or LITELLM_API_KEY) in backend/.env to enable image generation."
    return True, None


def _normalize_model_name(model_name: str) -> str:
    normalized = (model_name or "").strip()
    if normalized.startswith("models/"):
        normalized = normalized[len("models/") :]
    if normalized.startswith("gemini/"):
        normalized = normalized[len("gemini/") :]
    return normalized


def _parse_fallback_models() -> list[str]:
    configured = settings.image_generation_fallback_models or ""
    primary = _normalize_model_name(settings.gemini_image_model_name)
    models: list[str] = []
    for token in configured.split(","):
        normalized = _normalize_model_name(token)
        if not normalized or normalized == primary or normalized in models:
            continue
        models.append(normalized)
    return models

if DATABASE_AVAILABLE:
    @router.post("/chat", response_model=ChatResponse)
    async def chat(
        request: ChatRequest,
        raw_request: Request,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """Chat with the AI and store conversation"""
        from ..config import settings
        from sqlalchemy import select
        
        api_key = settings.litellm_api_key or settings.gemini_api_key
        if not api_key:
            raise HTTPException(status_code=500, detail="No Gemini or LiteLLM API key is configured in backend/.env")

        try:
            # Get thread-specific context messages from database unless reset is requested.
            if request.reset_history:
                context_messages = []
            elif request.thread_id:
                result = await db.execute(
                    select(ChatMessage)
                    .where(ChatMessage.user_id == current_user.id)
                    .where(ChatMessage.thread_id == request.thread_id)
                    .order_by(ChatMessage.created_at)
                )
                thread_messages = result.scalars().all()
                context_messages = [
                    {"role": msg.role, "content": msg.content}
                    for msg in thread_messages[-MEMORY_MESSAGE_LIMIT:]
                ]
            else:
                context_messages = []

            context_messages = _filter_context_messages_for_mode(context_messages, request.mode)

            attachment_context = _build_attachment_context(request.attachments)
            rag_chunks: list[dict] = []
            rag_context = None
            if request.mode == "rag":
                rag_chunks = await retrieve_relevant_chunks(
                    current_user.id,
                    request.message,
                    request.rag_attachment_ids,
                )
                if not rag_chunks and request.rag_attachment_ids:
                    # Backfill older uploads that were indexed with short previews.
                    attachment_result = await db.execute(
                        select(Attachment)
                        .where(Attachment.user_id == current_user.id)
                        .where(Attachment.id.in_(request.rag_attachment_ids))
                    )
                    selected_attachments = attachment_result.scalars().all()
                    for attachment in selected_attachments:
                        content = None
                        try:
                            content = await read_attachment_bytes(attachment.storage_key)
                        except Exception:
                            content = None

                        extracted_text = (attachment.text_content or "").strip()
                        is_pdf = attachment.mime_type == "application/pdf" or attachment.original_name.lower().endswith(".pdf")
                        if is_pdf and content:
                            extracted_text = extract_text_preview(content, "pdf", limit_chars=50000) or extracted_text

                        if extracted_text:
                            await index_attachment_chunks(attachment, extracted_text)

                    rag_chunks = await retrieve_relevant_chunks(
                        current_user.id,
                        request.message,
                        request.rag_attachment_ids,
                    )

                if not rag_chunks and request.rag_attachment_ids:
                    rag_chunks = await get_selected_attachment_chunks(
                        current_user.id,
                        request.rag_attachment_ids,
                        limit=max(1, settings.rag_top_k),
                    )
                rag_context = _build_rag_context(rag_chunks)
            stored_user_message = request.message.strip() or "Sent attachments"
            final_user_message = stored_user_message
            if attachment_context:
                final_user_message = f"{final_user_message}\n\n{attachment_context}"
            if rag_context:
                final_user_message = f"{final_user_message}\n\n{rag_context}"

            # Store user message with thread_id
            user_message = ChatMessage(
                user_id=current_user.id,
                thread_id=request.thread_id,
                role="user",
                content=stored_user_message
            )
            db.add(user_message)
            await db.commit()
            await db.refresh(user_message)

            # Link uploaded attachments to this user message and thread.
            upload_ids = [item.upload_id for item in request.attachments if item.upload_id is not None]
            if upload_ids:
                attachment_result = await db.execute(
                    select(Attachment)
                    .where(Attachment.user_id == current_user.id)
                    .where(Attachment.id.in_(upload_ids))
                )
                linked = attachment_result.scalars().all()
                for attachment in linked:
                    attachment.chat_message_id = user_message.id
                    attachment.thread_id = request.thread_id
                await db.commit()

            # Make RAG behavior explicitly interlinked with indexed chunks.
            if request.mode == "rag" and not rag_chunks:
                answer = (
                    "[RAG mode | chunks: 0]\n"
                    "No document context available. Upload or select a document in RAG mode, then ask again.\n\n"
                    "Sources: none (no selected indexed chunks matched this query)."
                )

                assistant_message = ChatMessage(
                    user_id=current_user.id,
                    thread_id=request.thread_id,
                    role="assistant",
                    content=answer,
                )
                db.add(assistant_message)
                await db.commit()

                return ChatResponse(answer=answer)

            # Configure client based on whether using LiteLLM proxy or direct Gemini API
            if settings.litellm_api_key and settings.litellm_proxy_url:
                # Use LiteLLM proxy
                client = OpenAI(
                    api_key=api_key,
                    base_url=settings.litellm_proxy_url,
                    timeout=LLM_TIMEOUT_SECONDS,
                    max_retries=1,
                )
                model_name = settings.gemini_model_name

            # Database chat: convert natural language to SQL and answer from Supabase when applicable.
            if request.mode in {"normal", "db"}:
                db_answer = await try_database_chat_answer(
                    question=stored_user_message,
                    db=db,
                    client=client,
                    model_name=model_name,
                )
                if db_answer:
                    prefix = "[DB mode]" if request.mode == "db" else "[Normal mode]"
                    answer = f"{prefix}\n{db_answer}"
                    assistant_message = ChatMessage(
                        user_id=current_user.id,
                        thread_id=request.thread_id,
                        role="assistant",
                        content=answer,
                    )
                    db.add(assistant_message)
                    await db.commit()
                    return ChatResponse(answer=answer)

                if request.mode == "db":
                    answer = (
                        "[DB mode]\n"
                        "I could not generate a safe database query for that request. "
                        "Please ask a data question using tables like users, chat_messages, attachments, "
                        "image_generations, or user_credentials."
                    )
                    assistant_message = ChatMessage(
                        user_id=current_user.id,
                        thread_id=request.thread_id,
                        role="assistant",
                        content=answer,
                    )
                    db.add(assistant_message)
                    await db.commit()
                    return ChatResponse(answer=answer)
            else:
                # Use direct Gemini API (not typical for OpenAI client, but kept for compatibility)
                client = OpenAI(
                    api_key=api_key,
                    timeout=LLM_TIMEOUT_SECONDS,
                    max_retries=1,
                )
                model_name = settings.gemini_model_name

            mode_system_instruction = (
                "Mode=RAG. Use retrieved snippets as the primary grounding source. "
                "If snippets are missing, say that indexed context was not found. "
                "End your answer with a short 'Sources:' line listing source names when available."
                if request.mode == "rag"
                else (
                    "Mode=DB. If this is not a database question, ask the user to switch mode."
                    if request.mode == "db"
                    else "Mode=NORMAL. Do not claim you used retrieved snippets or indexed document context."
                )
            )

            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"You are a helpful assistant. You are chatting with {current_user.name}. "
                            "When asked about previous questions, use the provided recent-question context exactly."
                            " If retrieved knowledge snippets are provided, ground your answer in them."
                        ),
                    },
                    {"role": "system", "content": mode_system_instruction},
                    {"role": "system", "content": _build_recent_questions_context(context_messages)},
                    *context_messages,
                    {"role": "user", "content": final_user_message}
                ],
                temperature=0.2,
                max_tokens=1024
            )

            answer = _strip_mode_metadata(_extract_assistant_text(response))
            if request.mode == "rag":
                if rag_chunks:
                    lowered = answer.lower()
                    if "no indexed context" in lowered or "indexed context was not found" in lowered or "no document context" in lowered:
                        chunk_snippets = [str(item.get("text") or "").strip() for item in rag_chunks[:2]]
                        merged = " ".join([snippet for snippet in chunk_snippets if snippet])
                        merged = re.sub(r"\s+", " ", merged).strip()
                        if merged:
                            answer = f"Based on your selected document(s): {merged[:500]}"

                    source_names = []
                    for chunk in rag_chunks:
                        source = str(chunk.get("source_name") or "unknown")
                        if source not in source_names:
                            source_names.append(source)
                    sources_line = ", ".join(source_names[:3])
                    answer = f"[RAG mode | chunks: {len(rag_chunks)}]\n{answer}\n\nSources: {sources_line}"
                else:
                    answer = f"[RAG mode | chunks: 0]\n{answer}\n\nSources: none (no indexed chunks matched this query)."
            elif request.mode == "normal":
                answer = f"[Normal mode]\n{answer}"
            else:
                answer = f"[DB mode]\n{answer}"

            # Store assistant message with thread_id
            assistant_message = ChatMessage(
                user_id=current_user.id,
                thread_id=request.thread_id,
                role="assistant",
                content=answer
            )
            db.add(assistant_message)
            await db.commit()

            return ChatResponse(answer=answer)

        except APITimeoutError as exc:
            print(f"ERROR: LLM timeout: {exc}")
            raise HTTPException(
                status_code=504,
                detail="The model took too long to respond. Please try again.",
            )
        except Exception as exc:
            print(f"ERROR in /chat endpoint: {type(exc).__name__}: {str(exc)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Error: {str(exc)}")

    @router.get("/history")
    async def get_chat_history(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """Get user's chat history"""
        from sqlalchemy import select

        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.user_id == current_user.id)
            .order_by(ChatMessage.created_at)
        )
        messages = result.scalars().all()

        message_ids = [msg.id for msg in messages]
        attachment_map: dict[int, list[dict]] = {}
        if message_ids:
            attachment_result = await db.execute(
                select(Attachment).where(Attachment.chat_message_id.in_(message_ids))
            )
            all_attachments = attachment_result.scalars().all()
            for item in all_attachments:
                if item.chat_message_id is None:
                    continue
                attachment_map.setdefault(item.chat_message_id, []).append(_serialize_attachment(item))

        return [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "thread_id": msg.thread_id,
                "created_at": msg.created_at.isoformat(),
                "attachments": attachment_map.get(msg.id, []),
            }
            for msg in messages
        ]

    @router.get("/history/sidebar")
    async def get_sidebar_history(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """Get thread-based history for the left sidebar."""
        from sqlalchemy import select, func

        # Get the first user message and last message for each thread
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.user_id == current_user.id)
            .order_by(ChatMessage.thread_id.desc(), ChatMessage.created_at)
        )
        all_messages = result.scalars().all()

        # Group by thread_id
        threads = {}
        for msg in all_messages:
            thread_id = msg.thread_id or 0
            if thread_id not in threads:
                threads[thread_id] = {
                    "id": thread_id,
                    "first_message": msg.content if msg.role == "user" else None,
                    "last_message": None,
                    "created_at": msg.created_at,
                }
            if msg.role == "user" and threads[thread_id]["first_message"] is None:
                threads[thread_id]["first_message"] = msg.content
            threads[thread_id]["last_message"] = msg.content

        # Build sidebar items
        sidebar_items = []
        for thread in sorted(threads.values(), key=lambda x: x["created_at"], reverse=True):
            title = (thread["first_message"][:80] if thread["first_message"] else "Chat") or "Chat"
            sidebar_items.append({
                "id": thread["id"],
                "title": title,
                "preview": (thread["last_message"][:100] if thread["last_message"] else "No messages") or "No messages",
                "created_at": thread["created_at"].isoformat(),
            })

        return sidebar_items

    @router.delete("/history/{thread_id}")
    async def delete_thread(
        thread_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """Delete a chat thread and all its messages"""
        from sqlalchemy import delete, select

        attachment_result = await db.execute(
            select(Attachment)
            .where(Attachment.user_id == current_user.id)
            .where(Attachment.thread_id == thread_id)
        )
        thread_attachments = attachment_result.scalars().all()
        for item in thread_attachments:
            await delete_attachment_blob(item.storage_key)

        await db.execute(
            delete(ImageGeneration)
            .where(ImageGeneration.user_id == current_user.id)
            .where(ImageGeneration.thread_id == thread_id)
        )

        await db.execute(
            delete(Attachment)
            .where(Attachment.user_id == current_user.id)
            .where(Attachment.thread_id == thread_id)
        )

        # Only delete messages that belong to the current user in the specified thread
        stmt = delete(ChatMessage).where(
            ChatMessage.user_id == current_user.id
        ).where(
            ChatMessage.thread_id == thread_id
        )
        await db.execute(stmt)
        await db.commit()

        return {"status": "deleted", "thread_id": thread_id}

    @router.post("/chat/image", response_model=ImageGenerationResponse)
    async def generate_image(
        request: ImageGenerationRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        enabled, reason = _is_image_generation_enabled()
        if not enabled:
            raise HTTPException(status_code=503, detail=reason or "Image generation is not enabled.")

        prompt = validate_prompt(request.prompt)
        enforce_generation_rate_limit(current_user.id)

        # Persist the user prompt as a normal user message to keep thread history consistent.
        user_message = ChatMessage(
            user_id=current_user.id,
            thread_id=request.thread_id,
            role="user",
            content=prompt,
        )
        db.add(user_message)
        await db.commit()
        await db.refresh(user_message)

        assistant_text = f"Generated image for: {prompt}"
        assistant_message = ChatMessage(
            user_id=current_user.id,
            thread_id=request.thread_id,
            role="assistant",
            content=assistant_text,
        )
        db.add(assistant_message)
        await db.commit()
        await db.refresh(assistant_message)

        generation = ImageGeneration(
            user_id=current_user.id,
            thread_id=request.thread_id,
            requested_by_message_id=user_message.id,
            result_message_id=assistant_message.id,
            prompt=prompt,
            status="pending",
        )
        db.add(generation)
        await db.commit()
        await db.refresh(generation)

        try:
            result = await generate_image_with_gemini(prompt)
            extension = _extension_for_mime(result.mime_type)
            filename = f"image-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}.{extension}"

            storage_key = await store_attachment_bytes(
                user_id=current_user.id,
                original_name=filename,
                content=result.image_bytes,
                mime_type=result.mime_type,
            )

            attachment = Attachment(
                user_id=current_user.id,
                thread_id=request.thread_id,
                chat_message_id=assistant_message.id,
                original_name=filename,
                storage_key=storage_key,
                mime_type=result.mime_type,
                category="image",
                file_size=len(result.image_bytes),
                text_content=result.revised_prompt,
            )
            db.add(attachment)
            await db.commit()
            await db.refresh(attachment)

            generation.status = "generated"
            generation.attachment_id = attachment.id
            generation.completed_at = datetime.utcnow()
            generation.error_message = None
            await db.commit()

            serialized = _serialize_attachment(attachment)
            return ImageGenerationResponse(
                answer=assistant_text,
                prompt=prompt,
                thread_id=request.thread_id,
                generation_id=generation.id,
                status=generation.status,
                image=ImageGenerationAttachmentResponse(
                    id=serialized["id"],
                    name=serialized["name"],
                    mime_type=serialized["mime_type"],
                    category=serialized["category"],
                    size=serialized["size"],
                    download_url=serialized["download_url"],
                ),
            )
        except HTTPException as exc:
            generation.status = "failed"
            generation.error_message = str(exc.detail)
            generation.completed_at = datetime.utcnow()
            assistant_message.content = f"Image generation failed: {exc.detail}"
            await db.commit()
            raise
        except Exception as exc:
            generation.status = "failed"
            generation.error_message = str(exc)
            generation.completed_at = datetime.utcnow()
            assistant_message.content = "Image generation failed due to an unexpected server error."
            await db.commit()
            raise HTTPException(status_code=500, detail="Image generation failed due to an unexpected server error.")

    @router.get("/chat/image/history")
    async def get_image_generation_history(
        thread_id: int | None = None,
        limit: int = 30,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        from sqlalchemy import select

        safe_limit = max(1, min(limit, 100))

        stmt = (
            select(ImageGeneration)
            .where(ImageGeneration.user_id == current_user.id)
            .order_by(ImageGeneration.created_at.desc())
            .limit(safe_limit)
        )
        if thread_id is not None:
            stmt = stmt.where(ImageGeneration.thread_id == thread_id)

        result = await db.execute(stmt)
        generations = result.scalars().all()

        attachment_ids = [g.attachment_id for g in generations if g.attachment_id is not None]
        attachment_map: dict[int, Attachment] = {}
        if attachment_ids:
            attachment_result = await db.execute(
                select(Attachment)
                .where(Attachment.user_id == current_user.id)
                .where(Attachment.id.in_(attachment_ids))
            )
            for attachment in attachment_result.scalars().all():
                attachment_map[attachment.id] = attachment

        items = []
        for generation in generations:
            attachment_payload = None
            if generation.attachment_id is not None and generation.attachment_id in attachment_map:
                attachment_payload = _serialize_attachment(attachment_map[generation.attachment_id])

            items.append(
                {
                    "id": generation.id,
                    "thread_id": generation.thread_id,
                    "prompt": generation.prompt,
                    "status": generation.status,
                    "error_message": generation.error_message,
                    "requested_by_message_id": generation.requested_by_message_id,
                    "result_message_id": generation.result_message_id,
                    "created_at": generation.created_at.isoformat() if generation.created_at else None,
                    "completed_at": generation.completed_at.isoformat() if generation.completed_at else None,
                    "image": attachment_payload,
                }
            )

        return {"items": items}

    @router.get("/chat/image/capabilities")
    async def get_image_capabilities(
        current_user: User = Depends(get_current_user)
    ):
        del current_user
        enabled, reason = _is_image_generation_enabled()
        primary_model = _normalize_model_name(settings.gemini_image_model_name)
        fallback_models = _parse_fallback_models()
        return {
            "available": enabled,
            "reason": reason,
            "model": settings.gemini_image_model_name,
            "normalized_model": primary_model,
            "fallback_models": fallback_models,
            "max_prompt_chars": settings.image_generation_max_prompt_chars,
            "rate_limit_per_minute": settings.image_generation_max_per_minute,
        }
else:
    # Fallback implementation without database
    @router.post("/chat", response_model=ChatResponse)
    def chat_fallback(request: ChatRequest, raw_request: Request):
        """Chat with the AI (without database storage)"""
        from ..config import settings

        api_key = settings.litellm_api_key or settings.gemini_api_key
        if not api_key:
            raise HTTPException(status_code=500, detail="No Gemini or LiteLLM API key is configured in backend/.env")

        try:
            session_key = _extract_session_key(raw_request)
            memory = _fallback_session_memory[session_key]
            if request.reset_history:
                memory.clear()

            # Configure client based on whether using LiteLLM proxy or direct Gemini API
            if settings.litellm_api_key and settings.litellm_proxy_url:
                # Use LiteLLM proxy
                client = OpenAI(
                    api_key=api_key,
                    base_url=settings.litellm_proxy_url,
                    timeout=LLM_TIMEOUT_SECONDS,
                    max_retries=1,
                )
                model_name = settings.gemini_model_name
            else:
                # Use direct Gemini API (not typical for OpenAI client, but kept for compatibility)
                client = OpenAI(
                    api_key=api_key,
                    timeout=LLM_TIMEOUT_SECONDS,
                    max_retries=1,
                )
                model_name = settings.gemini_model_name

            attachment_context = _build_attachment_context(request.attachments)
            stored_user_message = request.message.strip() or "Sent attachments"
            final_user_message = stored_user_message
            if attachment_context:
                final_user_message = f"{final_user_message}\n\n{attachment_context}"

            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant. When asked about previous questions, use the provided recent-question context exactly.",
                    },
                    {"role": "system", "content": _build_recent_questions_context(list(memory))},
                    *list(memory),
                    {"role": "user", "content": final_user_message}
                ],
                temperature=0.2,
                max_tokens=1024
            )

            answer = _extract_assistant_text(response)

            memory.append({"role": "user", "content": stored_user_message})
            memory.append({"role": "assistant", "content": answer})
            return ChatResponse(answer=answer)

        except APITimeoutError:
            raise HTTPException(
                status_code=504,
                detail="The model took too long to respond. Please try again.",
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error: {str(exc)}")

    @router.get("/history")
    def get_chat_history_fallback():
        """Get chat history (not available without database)"""
        return []

    @router.get("/history/sidebar")
    def get_sidebar_history_fallback():
        """Get sidebar history (not available without database)"""
        return []

    @router.post("/chat/image")
    async def generate_image_fallback(request: ImageGenerationRequest):
        del request
        raise HTTPException(status_code=503, detail="Image generation requires database-backed mode.")

    @router.get("/chat/image/history")
    async def get_image_generation_history_fallback():
        return {"items": []}

    @router.get("/chat/image/capabilities")
    async def get_image_capabilities_fallback():
        return {
            "available": False,
            "reason": "Image generation requires database-backed mode.",
            "model": settings.gemini_image_model_name,
            "normalized_model": _normalize_model_name(settings.gemini_image_model_name),
            "fallback_models": _parse_fallback_models(),
        }


@router.get("/rag/debug")
async def get_rag_debug(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get RAG debug information from the Chroma chunk index."""
    _ = db
    return await get_user_chunk_debug(user_id=current_user.id, sample_limit=5)