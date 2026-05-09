from __future__ import annotations

import base64
import hashlib
import hmac
import time


def _urlsafe_encode(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("utf-8").rstrip("=")


def _urlsafe_decode(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8")).decode("utf-8")


def create_download_token(attachment_id: int, user_id: int, secret_key: str, ttl_minutes: int) -> str:
    expires_at = int(time.time()) + (ttl_minutes * 60)
    payload = f"{attachment_id}:{user_id}:{expires_at}"
    signature = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return _urlsafe_encode(f"{payload}.{signature}")


def verify_download_token(token: str, attachment_id: int, user_id: int, secret_key: str) -> bool:
    try:
        decoded = _urlsafe_decode(token)
        payload, signature = decoded.rsplit(".", 1)
    except Exception:
        return False

    expected = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return False

    try:
        payload_attachment_id, payload_user_id, payload_expiry = payload.split(":")
        if int(payload_attachment_id) != attachment_id or int(payload_user_id) != user_id:
            return False
        return int(payload_expiry) >= int(time.time())
    except Exception:
        return False
