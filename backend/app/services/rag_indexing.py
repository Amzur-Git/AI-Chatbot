from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..config import settings

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "attachments"
_client = None
_collection = None


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    normalized = (text or "").strip()
    if not normalized:
        return []

    safe_chunk_size = max(200, chunk_size)
    safe_overlap = max(0, min(chunk_overlap, safe_chunk_size - 1))
    step = max(1, safe_chunk_size - safe_overlap)

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + safe_chunk_size)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start += step
    return chunks


def _build_client():
    import chromadb

    api_key = (settings.chroma_api_key or "").strip()
    tenant = (settings.chroma_tenant_id or "").strip()
    database = (settings.chroma_database or "").strip()
    host = (settings.chroma_host or "").strip()

    cloud_client = getattr(chromadb, "CloudClient", None)
    if cloud_client and api_key and tenant and database:
        return cloud_client(api_key=api_key, tenant=tenant, database=database)

    if host:
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            headers["x-chroma-token"] = api_key
        if tenant:
            headers["x-chroma-tenant"] = tenant
        if database:
            headers["x-chroma-database"] = database
        return chromadb.HttpClient(host=host, ssl=True, headers=headers or None)

    return chromadb.PersistentClient(path=settings.chroma_persist_dir)


def _get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection

    _client = _build_client()
    _collection = _client.get_or_create_collection(name=_COLLECTION_NAME)
    return _collection


def _index_attachment_chunks_sync(attachment, text: str) -> int:
    chunks = _chunk_text(
        text=text,
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
    )
    if not chunks:
        return 0

    collection = _get_collection()
    ids: list[str] = []
    metadatas: list[dict[str, Any]] = []
    for idx, _ in enumerate(chunks):
        ids.append(f"user-{attachment.user_id}-att-{attachment.id}-chunk-{idx}")
        metadatas.append(
            {
                "user_id": int(attachment.user_id),
                "attachment_id": int(attachment.id),
                "source_name": attachment.original_name,
                "mime_type": attachment.mime_type,
                "chunk_index": idx,
            }
        )

    collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)
    return len(chunks)


async def index_attachment_chunks(attachment, text: str) -> int:
    if not text:
        return 0
    try:
        return await asyncio.to_thread(_index_attachment_chunks_sync, attachment, text)
    except Exception as exc:
        logger.warning("RAG indexing failed for attachment_id=%s: %s", attachment.id, exc)
        return 0


def _delete_attachment_chunks_sync(user_id: int, attachment_id: int) -> None:
    collection = _get_collection()
    collection.delete(where={"$and": [{"user_id": int(user_id)}, {"attachment_id": int(attachment_id)}]})


async def delete_attachment_chunks(user_id: int, attachment_id: int) -> None:
    try:
        await asyncio.to_thread(_delete_attachment_chunks_sync, user_id, attachment_id)
    except Exception as exc:
        logger.warning(
            "RAG chunk delete failed for user_id=%s attachment_id=%s: %s",
            user_id,
            attachment_id,
            exc,
        )


def _get_user_chunk_debug_sync(user_id: int, sample_limit: int = 5) -> dict[str, Any]:
    collection = _get_collection()
    records = collection.get(
        where={"user_id": int(user_id)},
        include=["documents", "metadatas"],
    )

    ids = records.get("ids") or []
    docs = records.get("documents") or []
    metas = records.get("metadatas") or []

    samples: list[dict[str, Any]] = []
    for idx in range(min(sample_limit, len(ids))):
        meta = metas[idx] if idx < len(metas) and metas[idx] else {}
        doc = docs[idx] if idx < len(docs) and docs[idx] else ""
        samples.append(
            {
                "id": ids[idx],
                "attachment_id": meta.get("attachment_id"),
                "source_name": meta.get("source_name"),
                "chunk_index": meta.get("chunk_index"),
                "preview": str(doc)[:220],
            }
        )

    return {
        "collection": _COLLECTION_NAME,
        "total_chunks": len(ids),
        "sample_count": len(samples),
        "samples": samples,
    }


async def get_user_chunk_debug(user_id: int, sample_limit: int = 5) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(_get_user_chunk_debug_sync, user_id, sample_limit)
    except Exception as exc:
        logger.warning("RAG debug read failed for user_id=%s: %s", user_id, exc)
        return {
            "collection": _COLLECTION_NAME,
            "total_chunks": 0,
            "sample_count": 0,
            "samples": [],
            "error": str(exc),
        }


def _retrieve_relevant_chunks_sync(
    user_id: int,
    query_text: str,
    top_k: int,
    distance_threshold: float,
    attachment_ids: list[int] | None = None,
) -> list[dict[str, Any]]:
    collection = _get_collection()
    where_filter: dict[str, Any] = {"user_id": int(user_id)}
    if attachment_ids:
        normalized_ids = [int(item) for item in attachment_ids]
        where_filter = {
            "$and": [
                {"user_id": int(user_id)},
                {"attachment_id": {"$in": normalized_ids}},
            ]
        }

    response = collection.query(
        query_texts=[query_text],
        n_results=max(1, top_k),
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    documents = (response.get("documents") or [[]])[0]
    metadatas = (response.get("metadatas") or [[]])[0]
    distances = (response.get("distances") or [[]])[0]
    ids = (response.get("ids") or [[]])[0]

    results: list[dict[str, Any]] = []
    for idx, doc in enumerate(documents):
        distance = distances[idx] if idx < len(distances) else None
        if distance is not None and distance > distance_threshold:
            continue

        meta = metadatas[idx] if idx < len(metadatas) and metadatas[idx] else {}
        results.append(
            {
                "id": ids[idx] if idx < len(ids) else None,
                "text": str(doc),
                "distance": distance,
                "attachment_id": meta.get("attachment_id"),
                "source_name": meta.get("source_name"),
                "chunk_index": meta.get("chunk_index"),
            }
        )

    return results


async def retrieve_relevant_chunks(user_id: int, query_text: str, attachment_ids: list[int] | None = None) -> list[dict[str, Any]]:
    clean_query = (query_text or "").strip()
    if not clean_query:
        return []

    try:
        return await asyncio.to_thread(
            _retrieve_relevant_chunks_sync,
            user_id,
            clean_query,
            settings.rag_top_k,
            settings.rag_similarity_distance_threshold,
            attachment_ids,
        )
    except Exception as exc:
        logger.warning("RAG retrieval failed for user_id=%s: %s", user_id, exc)
        return []


def _get_selected_attachment_chunks_sync(user_id: int, attachment_ids: list[int], limit: int) -> list[dict[str, Any]]:
    if not attachment_ids:
        return []

    collection = _get_collection()
    records = collection.get(
        where={
            "$and": [
                {"user_id": int(user_id)},
                {"attachment_id": {"$in": [int(item) for item in attachment_ids]}},
            ]
        },
        include=["documents", "metadatas"],
    )

    ids = records.get("ids") or []
    docs = records.get("documents") or []
    metas = records.get("metadatas") or []

    items: list[dict[str, Any]] = []
    for idx in range(min(limit, len(ids))):
        meta = metas[idx] if idx < len(metas) and metas[idx] else {}
        doc = docs[idx] if idx < len(docs) else ""
        items.append(
            {
                "id": ids[idx],
                "text": str(doc),
                "distance": None,
                "attachment_id": meta.get("attachment_id"),
                "source_name": meta.get("source_name"),
                "chunk_index": meta.get("chunk_index"),
            }
        )
    return items


async def get_selected_attachment_chunks(user_id: int, attachment_ids: list[int], limit: int = 4) -> list[dict[str, Any]]:
    try:
        return await asyncio.to_thread(_get_selected_attachment_chunks_sync, user_id, attachment_ids, limit)
    except Exception as exc:
        logger.warning("RAG selected-chunk fallback failed for user_id=%s: %s", user_id, exc)
        return []
