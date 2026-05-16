from __future__ import annotations

import json
import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import get_settings
from app.models import DigestRequest
from app.runner import run_research_agent

load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title="Research Digest Agent",
    description="Autonomous AI research agent with LangGraph workflow and live SSE updates",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _sse_line(event_dict: dict) -> str:
    return f"data: {json.dumps(event_dict)}\\n\\n"


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "research-digest-agent",
        "version": "2.0.0",
    }


@app.post("/api/research")
async def research_digest(request: DigestRequest):
    topic = request.topic.strip()
    if not topic:
        raise HTTPException(status_code=422, detail="Topic must not be empty.")

    async def event_generator():
        try:
            async for event in run_research_agent(topic):
                yield _sse_line(event)
        except Exception as exc:
            logger.exception("Research workflow failed for topic '%s'", topic)
            yield _sse_line(
                {
                    "event": "error",
                    "data": {"message": str(exc)},
                }
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/example")
async def api_example():
    return JSONResponse(
        {
            "topic": "Retrieval Augmented Generation",
            "example": "curl -X POST http://127.0.0.1:8010/api/research -H 'Content-Type: application/json' -d '{\\\"topic\\\":\\\"Retrieval Augmented Generation\\\"}'",
        }
    )
