from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..models import Attachment, User
from ..services.attachment_storage import delete_attachment_blob, read_attachment_bytes, store_attachment_bytes
from ..services.attachment_tokens import create_download_token, verify_download_token
from ..services.rag_indexing import delete_attachment_chunks, index_attachment_chunks
from ..services.attachment_utils import extract_text_preview, infer_category, sanitize_filename, validate_upload

router = APIRouter()


def _allowed_extensions() -> list[str]:
    return [item.strip().lower() for item in settings.allowed_attachment_extensions.split(",") if item.strip()]


def _attachment_download_url(attachment_id: int, user_id: int) -> str:
    token = create_download_token(
        attachment_id=attachment_id,
        user_id=user_id,
        secret_key=settings.secret_key,
        ttl_minutes=settings.attachment_download_token_expire_minutes,
    )
    return f"/api/uploads/{attachment_id}/download?token={token}"


@router.post("/uploads")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a file for the current user and persist metadata."""

    contents = await file.read()
    ext = validate_upload(
        upload_file=file,
        size_bytes=len(contents),
        max_size_mb=settings.max_attachment_size_mb,
        allowed_extensions=_allowed_extensions(),
    )

    safe_name = sanitize_filename(file.filename or f"upload.{ext}")

    mime_type = file.content_type or "application/octet-stream"
    category = infer_category(ext)
    preview_limit = 50000 if ext == "pdf" else 5000
    preview = extract_text_preview(contents, ext, limit_chars=preview_limit)
    storage_key = await store_attachment_bytes(
        user_id=current_user.id,
        original_name=file.filename or safe_name,
        content=contents,
        mime_type=mime_type,
    )

    attachment = Attachment(
        user_id=current_user.id,
        chat_message_id=None,
        thread_id=None,
        storage_key=storage_key,
        original_name=file.filename or safe_name,
        mime_type=mime_type,
        category=category,
        file_size=len(contents),
        text_content=preview,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)

    if attachment.text_content:
        await index_attachment_chunks(attachment, attachment.text_content)

    return {
        "id": attachment.id,
        "name": attachment.original_name,
        "mime_type": attachment.mime_type,
        "category": attachment.category,
        "size": attachment.file_size,
        "text_content": attachment.text_content,
        "download_url": _attachment_download_url(attachment.id, current_user.id),
    }


@router.get("/uploads/{upload_id}/download")
async def download_file(
    upload_id: int,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Download attachment using a short-lived signed token."""

    result = await db.execute(select(Attachment).where(Attachment.id == upload_id))
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    if not verify_download_token(
        token=token,
        attachment_id=attachment.id,
        user_id=attachment.user_id,
        secret_key=settings.secret_key,
    ):
        raise HTTPException(status_code=403, detail="Invalid or expired download token")

    content = await read_attachment_bytes(attachment.storage_key)
    return Response(
        content=content,
        media_type=attachment.mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{attachment.original_name}"',
        },
    )


@router.delete("/uploads/{upload_id}")
async def delete_file(
    upload_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an uploaded file (only if owned by current user)."""

    result = await db.execute(
        select(Attachment).where(Attachment.id == upload_id).where(Attachment.user_id == current_user.id)
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    await delete_attachment_blob(attachment.storage_key)
    await delete_attachment_chunks(user_id=current_user.id, attachment_id=attachment.id)

    await db.execute(delete(Attachment).where(Attachment.id == attachment.id))
    await db.commit()
    return {"status": "deleted", "upload_id": upload_id}


async def cleanup_stale_unlinked_uploads(session: AsyncSession):
    """Cleanup unattached uploads older than configured TTL."""
    from datetime import datetime, timedelta

    cutoff = datetime.utcnow() - timedelta(hours=settings.unlinked_upload_ttl_hours)
    result = await session.execute(
        select(Attachment)
        .where(Attachment.chat_message_id.is_(None))
        .where(Attachment.created_at < cutoff)
    )
    stale_attachments = result.scalars().all()

    removed = 0
    for item in stale_attachments:
        await delete_attachment_blob(item.storage_key)
        await delete_attachment_chunks(user_id=item.user_id, attachment_id=item.id)
        await session.execute(delete(Attachment).where(Attachment.id == item.id))
        removed += 1

    if removed:
        await session.commit()
    return removed
