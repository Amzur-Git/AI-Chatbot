from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=(".env", "../backend/.env", "../.env"),
        env_file_encoding="utf-8",
    )
    app_name: str = "AI Data Query API"
    app_env: str = "development"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8001

    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    upload_dir: Path = Field(default=Path("app/uploads"))
    max_upload_mb: int = 50

    session_ttl_minutes: int = 60
    history_max_messages: int = 20

    llm_model: str = "gpt-4o"
    openai_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "LITELLM_API_KEY"),
    )
    openai_base_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_BASE_URL", "LITELLM_PROXY_URL"),
    )
    openai_temperature: float = 0.0
    llm_timeout_seconds: int = 120

    google_service_account_file: Optional[str] = None
    google_service_account_json: Optional[str] = None

    api_key: Optional[str] = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
