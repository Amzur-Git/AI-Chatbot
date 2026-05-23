from pathlib import Path
from typing import Optional
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    litellm_proxy_url: Optional[str] = "https://litellm.amzur.com"
    litellm_api_key: Optional[str]
    litellm_user_id: Optional[str]
    gemini_api_key: Optional[str]
    openai_api_key: Optional[str] = None
    chroma_api_key: Optional[str] = None
    chroma_tenant_id: Optional[str] = None
    chroma_database: Optional[str] = None
    chroma_host: str = "api.trychroma.com"
    supabase_url: Optional[str] = None
    supabase_service_role_key: Optional[str] = None
    supabase_storage_bucket: str = "attachments"
    gemini_model_name: str = "gemini/gemini-2.5-flash"
    gemini_image_model_name: str = Field(
        default="gemini-2.0-flash-preview-image-generation",
        validation_alias=AliasChoices("IMAGE_GEN_MODEL", "GEMINI_IMAGE_MODEL_NAME"),
    )
    image_generation_fallback_models: str = Field(
        default="gemini-2.5-flash-image",
        validation_alias=AliasChoices("IMAGE_GEN_FALLBACK_MODELS", "GEMINI_IMAGE_FALLBACK_MODELS"),
    )
    image_generation_timeout_seconds: float = 90.0
    image_generation_max_prompt_chars: int = 1000
    image_generation_max_per_minute: int = 10
    image_generation_store_path_prefix: str = "generated-images"
    openai_embedding_model: str = "text-embedding-3-large"
    rag_chunk_size: int = 1200
    rag_chunk_overlap: int = 200
    rag_top_k: int = 4
    rag_similarity_distance_threshold: float = 1.2
    db_chat_max_rows: int = 100
    db_chat_schema_max_tables: int = 40
    db_chat_schema_max_columns_per_table: int = 25
    db_chat_allowed_schemas: str = "public"
    db_chat_allowed_tables: str = ""
    database_url: str = "postgresql://localhost/chatbot_db"
    google_client_id: Optional[str]
    google_client_secret: Optional[str]
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    google_service_account_json: Optional[str] = None
    frontend_base_url: str = "http://localhost:5174"
    allowed_email_domain: str = "amzur.com"
    chroma_persist_dir: str = "./chroma_db"

    # n8n ticket workflow integration
    n8n_webhook_url: Optional[str] = "http://localhost:5678/webhook/ticket-automation"
    n8n_webhook_secret: Optional[str] = None
    n8n_closed_ticket_webhook_url: Optional[str] = None

    # SMTP settings for backend notification emails
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True
    smtp_from_email: Optional[str] = None

    # JWT settings
    secret_key: str = "your-secret-key-here-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Attachment upload settings
    upload_storage_dir: str = "uploads"
    attachment_download_token_expire_minutes: int = 15
    max_attachment_size_mb: int = 20
    allowed_attachment_extensions: str = "png,jpg,jpeg,webp,gif,mp4,mov,webm,csv,xlsx,pdf,tex,latex,py,js,ts,java,cpp,json,sql"
    unlinked_upload_ttl_hours: int = 24
    attachment_scan_mode: str = "basic"
    attachment_scan_fail_open: bool = False
    attachment_scan_timeout_seconds: float = 10.0
    clamav_host: str = "127.0.0.1"
    clamav_port: int = 3310

    class Config:
        env_file = BASE_DIR / ".env"

settings = Settings()