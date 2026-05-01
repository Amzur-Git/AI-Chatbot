from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.exc import SQLAlchemyError
from .routes import auth, chat

# Try to import database components, but make them optional
try:
    from .database import engine
    from .models import Base
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    print("Warning: Database dependencies not available. Running without database.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    if DATABASE_AVAILABLE:
        # Create database tables. Under reload, concurrent startup can race.
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except SQLAlchemyError as exc:
            print(f"Warning: database initialization issue ignored: {exc}")
    yield

app = FastAPI(
    title="Gemini Chatbot with Database",
    version="0.2.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://localhost:5173"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(chat.router, prefix="/api", tags=["chat"])

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