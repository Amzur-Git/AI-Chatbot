import json
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.exc import SQLAlchemyError
from .routes import auth, chat

try:
    from .routes import uploads
    from .routes.uploads import cleanup_stale_unlinked_uploads
    UPLOADS_AVAILABLE = True
except ImportError:
    uploads = None
    UPLOADS_AVAILABLE = False

    async def cleanup_stale_unlinked_uploads(_session):
        return 0

try:
    from .services.file_scan import get_scanner_health
except ImportError:
    def get_scanner_health():
        return {"mode": "unavailable", "healthy": False}

logger = logging.getLogger("backend.startup")

# Try to import database components, but make them optional
try:
    from .database import engine
    from .database import async_session
    from .models import Base
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    logger.warning("Database dependencies not available. Running without database.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    scanner_health = get_scanner_health()
    logger.info(
        "startup.scanner_health %s",
        json.dumps(scanner_health, ensure_ascii=True, separators=(",", ":")),
    )

    if DATABASE_AVAILABLE:
        # Create database tables. Under reload, concurrent startup can race.
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                # Backward-compatible schema patch for existing attachments tables.
                await conn.exec_driver_sql("ALTER TABLE IF EXISTS attachments ADD COLUMN IF NOT EXISTS thread_id INTEGER")
                await conn.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS ix_attachments_thread_id ON attachments (thread_id)"
                )

            async with async_session() as session:
                removed = await cleanup_stale_unlinked_uploads(session)
                if removed:
                    logger.info(
                        "startup.unlinked_upload_cleanup %s",
                        json.dumps({"removed": removed}, ensure_ascii=True, separators=(",", ":")),
                    )
        except SQLAlchemyError as exc:
            logger.warning("Database initialization issue ignored: %s", exc)
    yield

app = FastAPI(
    title="Gemini Chatbot with Database",
    version="0.2.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:5176", "http://localhost:5177", "http://localhost:5178"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
if UPLOADS_AVAILABLE:
    app.include_router(uploads.router, prefix="/api", tags=["uploads"])

@app.get("/")
def read_root():
    status = "with database" if DATABASE_AVAILABLE else "without database"
    return {"message": f"Gemini chatbot backend running {status}."}

# Legacy endpoint for backward compatibility
@app.post("/api/chat/legacy")
def legacy_chat():
    raise HTTPException(
        status_code=410,
        detail="This endpoint is deprecated. Please use /api/chat with authentication."
    )