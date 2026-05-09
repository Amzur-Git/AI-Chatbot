from __future__ import annotations

from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import httpx
from fastapi import HTTPException

from ..config import settings
from .attachment_utils import sanitize_filename


LOCAL_UPLOAD_DIR = Path(settings.upload_storage_dir)
LOCAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _is_supabase_enabled() -> bool:
    return bool(
        settings.supabase_url
        and settings.supabase_service_role_key
        and settings.supabase_storage_bucket
    )


def _is_supabase_key(storage_key: str) -> bool:
    return storage_key.startswith("supabase://")


def _split_supabase_key(storage_key: str) -> tuple[str, str]:
    value = storage_key.removeprefix("supabase://")
    parts = value.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise HTTPException(status_code=500, detail="Invalid Supabase storage key")
    return parts[0], parts[1]


def _supabase_headers() -> dict[str, str]:
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }


async def store_attachment_bytes(
    user_id: int,
    original_name: str,
    content: bytes,
    mime_type: str,
) -> str:
    safe_name = sanitize_filename(original_name)
    object_name = f"{uuid4().hex}_{safe_name}"

    if _is_supabase_enabled():
        object_path = f"user_{user_id}/{object_name}"
        encoded_path = quote(object_path, safe="/")
        encoded_bucket = quote(settings.supabase_storage_bucket, safe="")
        url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{encoded_bucket}/{encoded_path}"
        headers = {
            **_supabase_headers(),
            "Content-Type": mime_type or "application/octet-stream",
            "x-upsert": "false",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, content=content)
        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Supabase upload failed ({response.status_code})",
            )

        return f"supabase://{settings.supabase_storage_bucket}/{object_path}"

    user_dir = LOCAL_UPLOAD_DIR / f"user_{user_id}"
    user_dir.mkdir(parents=True, exist_ok=True)
    file_path = user_dir / object_name
    file_path.write_bytes(content)
    return str(file_path)


async def read_attachment_bytes(storage_key: str) -> bytes:
    if _is_supabase_key(storage_key):
        bucket, object_path = _split_supabase_key(storage_key)
        encoded_bucket = quote(bucket, safe="")
        encoded_path = quote(object_path, safe="/")
        url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{encoded_bucket}/{encoded_path}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=_supabase_headers())
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Attachment file missing")
        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Supabase download failed ({response.status_code})",
            )
        return response.content

    file_path = Path(storage_key)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Attachment file missing")
    return file_path.read_bytes()


async def delete_attachment_blob(storage_key: str) -> None:
    if _is_supabase_key(storage_key):
        bucket, object_path = _split_supabase_key(storage_key)
        encoded_bucket = quote(bucket, safe="")
        encoded_path = quote(object_path, safe="/")
        url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{encoded_bucket}/{encoded_path}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(url, headers=_supabase_headers())

        if response.status_code not in (200, 204, 404):
            raise HTTPException(
                status_code=502,
                detail=f"Supabase delete failed ({response.status_code})",
            )
        return

    file_path = Path(storage_key)
    if file_path.exists():
        file_path.unlink()