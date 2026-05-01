from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    litellm_proxy_url: Optional[str] = "https://litellm.amzur.com"
    litellm_api_key: Optional[str]
    litellm_user_id: Optional[str]
    gemini_api_key: Optional[str]
    gemini_model_name: str = "gemini/gemini-2.5-flash"
    database_url: str = "postgresql://localhost/chatbot_db"
    google_client_id: Optional[str]
    google_client_secret: Optional[str]
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    frontend_base_url: str = "http://localhost:5174"
    allowed_email_domain: str = "amzur.com"
    chroma_persist_dir: str = "./chroma_db"

    # JWT settings
    secret_key: str = "your-secret-key-here-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    class Config:
        env_file = BASE_DIR / ".env"

settings = Settings()