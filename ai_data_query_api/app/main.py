from __future__ import annotations

import logging
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.logging_config import configure_logging
from app.config.settings import settings
from app.routes.data_routes import router as data_router
from app.services.query_agent import DataQueryAgentService
from app.services.session_store import InMemorySessionStore

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Production-ready AI Data Query API with FastAPI, Pandas, LangChain, and Google Sheets.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    started = perf_counter()
    response = await call_next(request)
    duration_ms = (perf_counter() - started) * 1000
    logger.info("%s %s -> %s (%.2f ms)", request.method, request.url.path, response.status_code, duration_ms)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    logger.exception("Unhandled exception")
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.on_event("startup")
async def on_startup() -> None:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    app.state.settings = settings
    app.state.session_store = InMemorySessionStore(
        ttl_minutes=settings.session_ttl_minutes,
        history_max_messages=settings.history_max_messages,
    )
    app.state.query_agent = DataQueryAgentService(settings=settings)
    logger.info("%s started", settings.app_name)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(data_router)
