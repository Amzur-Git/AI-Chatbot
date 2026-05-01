from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from openai import OpenAI

# Try to import database components
try:
    from sqlalchemy.ext.asyncio import AsyncSession
    from ..database import get_db
    from ..models import User, ChatMessage
    from ..auth import get_current_user
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

router = APIRouter()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    answer: str


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

if DATABASE_AVAILABLE:
    @router.post("/chat", response_model=ChatResponse)
    async def chat(
        request: ChatRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """Chat with the AI and store conversation"""
        from ..config import settings

        api_key = settings.litellm_api_key or settings.gemini_api_key
        if not api_key:
            raise HTTPException(status_code=500, detail="No Gemini or LiteLLM API key is configured in backend/.env")

        try:
            # Store user message
            user_message = ChatMessage(
                user_id=current_user.id,
                role="user",
                content=request.message
            )
            db.add(user_message)
            await db.commit()

            # Configure client based on whether using LiteLLM proxy or direct Gemini API
            if settings.litellm_api_key and settings.litellm_proxy_url:
                # Use LiteLLM proxy
                client = OpenAI(
                    api_key=api_key,
                    base_url=settings.litellm_proxy_url
                )
                model_name = settings.gemini_model_name
            else:
                # Use direct Gemini API (not typical for OpenAI client, but kept for compatibility)
                client = OpenAI(api_key=api_key)
                model_name = settings.gemini_model_name

            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": request.message}
                ],
                temperature=0.2,
                max_tokens=1024
            )

            answer = response.choices[0].message.content

            # Store assistant message
            assistant_message = ChatMessage(
                user_id=current_user.id,
                role="assistant",
                content=answer
            )
            db.add(assistant_message)
            await db.commit()

            return ChatResponse(answer=answer)

        except Exception as exc:
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

        return [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat()
            }
            for msg in messages
        ]

    @router.get("/history/sidebar")
    async def get_sidebar_history(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """Get compact user-centric history for the left sidebar."""
        from sqlalchemy import select

        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.user_id == current_user.id)
            .order_by(ChatMessage.created_at)
        )
        messages = result.scalars().all()

        return _build_sidebar_items(messages)
else:
    # Fallback implementation without database
    @router.post("/chat", response_model=ChatResponse)
    def chat_fallback(request: ChatRequest):
        """Chat with the AI (without database storage)"""
        from ..config import settings

        api_key = settings.litellm_api_key or settings.gemini_api_key
        if not api_key:
            raise HTTPException(status_code=500, detail="No Gemini or LiteLLM API key is configured in backend/.env")

        try:
            # Configure client based on whether using LiteLLM proxy or direct Gemini API
            if settings.litellm_api_key and settings.litellm_proxy_url:
                # Use LiteLLM proxy
                client = OpenAI(
                    api_key=api_key,
                    base_url=settings.litellm_proxy_url
                )
                model_name = settings.gemini_model_name
            else:
                # Use direct Gemini API (not typical for OpenAI client, but kept for compatibility)
                client = OpenAI(api_key=api_key)
                model_name = settings.gemini_model_name

            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": request.message}
                ],
                temperature=0.2,
                max_tokens=1024
            )

            answer = response.choices[0].message.content
            return ChatResponse(answer=answer)

        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error: {str(exc)}")

    @router.get("/history")
    def get_chat_history_fallback():
        """Get chat history (not available without database)"""
        return {"message": "Chat history not available - database not configured"}

    @router.get("/history/sidebar")
    def get_sidebar_history_fallback():
        """Get sidebar history (not available without database)"""
        return {"message": "Sidebar history not available - database not configured"}