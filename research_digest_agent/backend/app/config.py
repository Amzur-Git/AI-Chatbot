from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    cors_origins: list[str]


def get_settings() -> Settings:
    origins = os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:8010,http://127.0.0.1:8010,http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173",
    )
    return Settings(
        llm_api_key=os.environ.get("LITELLM_API_KEY", ""),
        llm_base_url=os.environ.get("LITELLM_PROXY_URL", "https://api.openai.com/v1"),
        llm_model=os.environ.get("LLM_MODEL", "gpt-4o"),
        cors_origins=[x.strip() for x in origins.split(",") if x.strip()],
    )
