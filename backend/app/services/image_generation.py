from __future__ import annotations

from collections import defaultdict, deque
import base64
from dataclasses import dataclass
from datetime import datetime
import time

import httpx
from fastapi import HTTPException

from ..config import settings


_RATE_WINDOW_SECONDS = 60
_user_generation_timestamps: dict[int, deque[float]] = defaultdict(deque)


@dataclass
class GeneratedImageResult:
    image_bytes: bytes
    mime_type: str
    revised_prompt: str | None = None


def _clean_prompt(prompt: str) -> str:
    return prompt.strip()


def validate_prompt(prompt: str) -> str:
    cleaned = _clean_prompt(prompt)
    if not cleaned:
        raise HTTPException(status_code=400, detail="Image prompt cannot be empty.")

    if len(cleaned) > settings.image_generation_max_prompt_chars:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Image prompt is too long. Maximum allowed is "
                f"{settings.image_generation_max_prompt_chars} characters."
            ),
        )

    return cleaned


def enforce_generation_rate_limit(user_id: int) -> None:
    now = time.time()
    history = _user_generation_timestamps[user_id]

    while history and now - history[0] > _RATE_WINDOW_SECONDS:
        history.popleft()

    if len(history) >= settings.image_generation_max_per_minute:
        raise HTTPException(
            status_code=429,
            detail="Image generation rate limit reached. Please try again in a minute.",
        )

    history.append(now)


def _extract_image_from_response(payload: dict) -> GeneratedImageResult:
    candidates = payload.get("candidates") or []
    for candidate in candidates:
        content = candidate.get("content") or {}
        parts = content.get("parts") or []
        revised_prompt: str | None = None

        for part in parts:
            text_part = part.get("text")
            if isinstance(text_part, str) and text_part.strip():
                revised_prompt = text_part.strip()

            inline_data = part.get("inlineData")
            if not inline_data:
                continue

            data = inline_data.get("data")
            mime = inline_data.get("mimeType") or "image/png"
            if not isinstance(data, str) or not data:
                continue

            try:
                image_bytes = base64.b64decode(data)
            except Exception as exc:
                raise HTTPException(status_code=502, detail="Failed to decode generated image response.") from exc

            return GeneratedImageResult(
                image_bytes=image_bytes,
                mime_type=mime,
                revised_prompt=revised_prompt,
            )

    raise HTTPException(status_code=502, detail="Gemini did not return an image for this prompt.")


def _extract_image_from_predict_response(payload: dict) -> GeneratedImageResult:
    predictions = payload.get("predictions") or []
    for item in predictions:
        if not isinstance(item, dict):
            continue

        # Common Imagen response field names.
        for field_name in ("bytesBase64Encoded", "imageBytes", "image"):
            encoded = item.get(field_name)
            if not isinstance(encoded, str) or not encoded:
                continue

            try:
                image_bytes = base64.b64decode(encoded)
            except Exception as exc:
                raise HTTPException(status_code=502, detail="Failed to decode Imagen predict response.") from exc

            return GeneratedImageResult(image_bytes=image_bytes, mime_type="image/png")

        # Some responses may nest the image payload.
        nested = item.get("output")
        if isinstance(nested, dict):
            encoded = nested.get("bytesBase64Encoded")
            if isinstance(encoded, str) and encoded:
                try:
                    image_bytes = base64.b64decode(encoded)
                except Exception as exc:
                    raise HTTPException(status_code=502, detail="Failed to decode Imagen predict response.") from exc
                return GeneratedImageResult(image_bytes=image_bytes, mime_type="image/png")

    raise HTTPException(status_code=502, detail="Imagen predict did not return an image.")


def _normalize_model_name(model_name: str) -> str:
    normalized = model_name.strip()
    if normalized.startswith("models/"):
        normalized = normalized[len("models/") :]
    if normalized.startswith("gemini/"):
        normalized = normalized[len("gemini/") :]
    return normalized


def _candidate_fallback_models(primary_model_name: str) -> list[str]:
    configured = settings.image_generation_fallback_models or ""
    candidates: list[str] = []
    for token in configured.split(","):
        normalized = _normalize_model_name(token)
        if not normalized:
            continue
        if normalized == primary_model_name:
            continue
        if normalized in candidates:
            continue
        candidates.append(normalized)
    return candidates


def _extract_error_detail(response: httpx.Response) -> str:
    detail = "Image generation failed."
    try:
        error_payload = response.json()
        error_detail = error_payload.get("error", {}).get("message")
        if isinstance(error_detail, str) and error_detail:
            return error_detail
    except Exception:
        pass

    fallback = (response.text or "").strip()
    if fallback:
        detail = fallback[:600]
    return detail


def _decode_image_base64(encoded: str) -> bytes:
    normalized = encoded.strip()
    # Support data URLs such as: data:image/png;base64,....
    if normalized.startswith("data:") and "," in normalized:
        normalized = normalized.split(",", 1)[1]

    try:
        return base64.b64decode(normalized)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Failed to decode LiteLLM image response.") from exc


async def _extract_image_from_litellm_response(payload: dict, timeout_seconds: float) -> GeneratedImageResult:
    """Parse OpenAI-compatible /v1/images/generations responses from LiteLLM."""
    data = payload.get("data")
    if isinstance(data, dict):
        items = [data]
    elif isinstance(data, list):
        items = data
    else:
        items = []

    # Fallback for non-standard wrappers.
    if not items:
        if isinstance(payload.get("images"), list):
            items = payload.get("images")
        elif isinstance(payload.get("image"), dict):
            items = [payload.get("image")]

    for item in items:
        if not isinstance(item, dict):
            continue

        for key in ("b64_json", "b64", "base64", "image_base64", "image"):
            encoded = item.get(key)
            if isinstance(encoded, str) and encoded.strip():
                return GeneratedImageResult(image_bytes=_decode_image_base64(encoded), mime_type="image/png")

        for key in ("url", "image_url"):
            image_url = item.get(key)
            if not isinstance(image_url, str) or not image_url.strip():
                continue

            try:
                async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                    image_response = await client.get(image_url)
            except httpx.HTTPError as exc:
                raise HTTPException(status_code=502, detail="Failed to fetch image URL returned by LiteLLM.") from exc

            if image_response.status_code >= 400:
                raise HTTPException(
                    status_code=502,
                    detail=f"LiteLLM image URL fetch failed ({image_response.status_code}).",
                )

            mime_type = image_response.headers.get("Content-Type", "image/png").split(";", 1)[0].strip()
            return GeneratedImageResult(image_bytes=image_response.content, mime_type=mime_type or "image/png")

    keys = ",".join(sorted(payload.keys()))
    raise HTTPException(status_code=502, detail=f"LiteLLM did not return image data. Response keys: {keys}")


async def _request_image_via_litellm(prompt: str) -> GeneratedImageResult:
    """Call the LiteLLM proxy /v1/images/generations endpoint."""
    litellm_key = settings.litellm_api_key
    litellm_url = settings.litellm_proxy_url
    if not litellm_key or not litellm_url:
        raise HTTPException(status_code=503, detail="LiteLLM proxy is not configured.")

    # Use the raw configured model name (e.g. gemini/imagen-4.0-fast-generate-001)
    model_name = (settings.gemini_image_model_name or "").strip()

    request_payload = {
        "model": model_name,
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "response_format": "b64_json",
    }

    headers = {"Authorization": f"Bearer {litellm_key}"}
    url = litellm_url.rstrip("/") + "/v1/images/generations"

    try:
        async with httpx.AsyncClient(timeout=settings.image_generation_timeout_seconds) as client:
            response = await client.post(url, json=request_payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Image generation request timed out.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Failed to reach LiteLLM image generation service.") from exc

    if response.status_code == 429:
        raise HTTPException(status_code=429, detail="Image generation quota exceeded. Please try again later.")
    if response.status_code >= 500:
        raise HTTPException(status_code=502, detail="LiteLLM service is temporarily unavailable.")
    if response.status_code >= 400:
        detail = _extract_error_detail(response)
        lower = detail.lower()
        if "safety" in lower or "blocked" in lower:
            raise HTTPException(status_code=400, detail="Prompt was blocked by safety filters.")
        raise HTTPException(status_code=400, detail=detail)

    parsed_payload = response.json()
    try:
        return await _extract_image_from_litellm_response(
            payload=parsed_payload,
            timeout_seconds=settings.image_generation_timeout_seconds,
        )
    except HTTPException as parse_exc:
        # Some LiteLLM providers return HTTP 200 with empty image fields when
        # response_format is not honored. Retry once with a minimal payload.
        if "did not return image data" not in str(parse_exc.detail).lower():
            raise

        retry_payload = {
            "model": model_name,
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024",
        }
        try:
            async with httpx.AsyncClient(timeout=settings.image_generation_timeout_seconds) as client:
                retry_response = await client.post(url, json=retry_payload, headers=headers)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Failed to reach LiteLLM image generation service.") from exc

        if retry_response.status_code == 429:
            raise HTTPException(status_code=429, detail="Image generation quota exceeded. Please try again later.")
        if retry_response.status_code >= 500:
            raise HTTPException(status_code=502, detail="LiteLLM service is temporarily unavailable.")
        if retry_response.status_code >= 400:
            detail = _extract_error_detail(retry_response)
            raise HTTPException(status_code=400, detail=detail)

        return await _extract_image_from_litellm_response(
            payload=retry_response.json(),
            timeout_seconds=settings.image_generation_timeout_seconds,
        )


async def _request_image_for_model(api_key: str, model_name: str, prompt: str) -> GeneratedImageResult:
    use_predict_endpoint = model_name.startswith("imagen-")

    if use_predict_endpoint:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:predict"
        request_payload = {
            "instances": [
                {"prompt": prompt},
            ],
            "parameters": {
                "sampleCount": 1,
            },
        }
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        request_payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                    ],
                }
            ],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
            },
        }

    params = {"key": api_key}

    try:
        async with httpx.AsyncClient(timeout=settings.image_generation_timeout_seconds) as client:
            response = await client.post(url, params=params, json=request_payload)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Image generation request timed out.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Failed to reach Gemini image generation service.") from exc

    if response.status_code == 429:
        raise HTTPException(status_code=429, detail="Gemini image quota exceeded. Please try again later.")

    if response.status_code >= 500:
        raise HTTPException(status_code=502, detail="Gemini service is temporarily unavailable.")

    if response.status_code >= 400:
        detail = _extract_error_detail(response)
        lower_detail = detail.lower()
        if "only available on paid plans" in lower_detail or "upgrade your account" in lower_detail:
            raise HTTPException(
                status_code=402,
                detail="The configured Imagen model requires a paid Google AI plan for this API key.",
            )
        if "safety" in lower_detail or "blocked" in lower_detail:
            raise HTTPException(status_code=400, detail="Prompt was blocked by Gemini safety filters.")
        if "quota exceeded" in lower_detail:
            raise HTTPException(status_code=429, detail="Gemini image quota exceeded. Please try again later.")
        raise HTTPException(status_code=400, detail=detail)

    payload = response.json()
    if use_predict_endpoint:
        return _extract_image_from_predict_response(payload)
    return _extract_image_from_response(payload)


async def generate_image_with_gemini(prompt: str) -> GeneratedImageResult:
    litellm_key = settings.litellm_api_key
    litellm_url = settings.litellm_proxy_url

    cleaned_prompt = validate_prompt(prompt)

    # Prefer LiteLLM proxy when configured — it has billing and supports Imagen models.
    if litellm_key and litellm_url:
        return await _request_image_via_litellm(cleaned_prompt)

    # Direct Gemini API fallback.
    api_key = settings.gemini_api_key
    if not api_key:
        raise HTTPException(status_code=503, detail="Gemini image generation is not configured.")

    model_name = _normalize_model_name(settings.gemini_image_model_name)

    try:
        return await _request_image_for_model(api_key=api_key, model_name=model_name, prompt=cleaned_prompt)
    except HTTPException as primary_exc:
        if primary_exc.status_code != 402 or not model_name.startswith("imagen-"):
            raise

        fallback_errors: list[str] = []
        for fallback_model in _candidate_fallback_models(model_name):
            try:
                return await _request_image_for_model(
                    api_key=api_key,
                    model_name=fallback_model,
                    prompt=cleaned_prompt,
                )
            except HTTPException as fallback_exc:
                fallback_errors.append(f"{fallback_model}: {fallback_exc.detail}")

        if fallback_errors:
            raise HTTPException(
                status_code=402,
                detail=(
                    "Configured Imagen model requires a paid Google AI plan and all fallback models failed. "
                    + " | ".join(fallback_errors)
                ),
            )

        raise primary_exc
