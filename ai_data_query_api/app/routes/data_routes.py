from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.config.settings import Settings
from app.models.schemas import (
    AskRequest,
    AskResponse,
    ChatHistoryResponse,
    LoadGoogleSheetRequest,
    LoadGoogleSheetResponse,
    UploadFileResponse,
)
from app.services.data_loader import load_file_to_dataframes
from app.services.google_sheet_loader import load_google_sheet_to_dataframes
from app.services.query_agent import DataQueryAgentService
from app.services.session_store import InMemorySessionStore
from app.utils.dataframe_utils import summarize_dataframe
from app.utils.security import validate_api_key

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Data Query"])


def _get_store(request: Request) -> InMemorySessionStore:
    return request.app.state.session_store


def _get_settings(request: Request) -> Settings:
    return request.app.state.settings


def _get_agent(request: Request) -> DataQueryAgentService:
    return request.app.state.query_agent


@router.post("/upload-file", response_model=UploadFileResponse, dependencies=[Depends(validate_api_key)])
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    session_id: Annotated[str | None, Form()] = None,
) -> UploadFileResponse:
    store = _get_store(request)
    settings = _get_settings(request)

    session = store.create_or_get_session(session_id)
    try:
        source_name, dataframes, active_sheet = await asyncio.wait_for(
            load_file_to_dataframes(
                file=file,
                upload_dir=settings.upload_dir,
                max_upload_mb=settings.max_upload_mb,
            ),
            timeout=120,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="File processing timed out. Try a smaller file.") from exc

    dataset = store.add_dataset(
        session_id=session.session_id,
        source_name=source_name,
        dataframes=dataframes,
        active_sheet=active_sheet,
    )

    summary = summarize_dataframe(dataframes[active_sheet])
    return UploadFileResponse(
        session_id=session.session_id,
        dataset_id=dataset.dataset_id,
        source_name=source_name,
        rows=summary["rows"],
        columns=summary["columns"],
        sheets=list(dataframes.keys()),
    )


@router.post("/load-google-sheet", response_model=LoadGoogleSheetResponse, dependencies=[Depends(validate_api_key)])
async def load_google_sheet(request: Request, payload: LoadGoogleSheetRequest) -> LoadGoogleSheetResponse:
    store = _get_store(request)
    settings = _get_settings(request)

    session = store.create_or_get_session(payload.session_id)
    sheet_input = payload.google_sheet_id or payload.google_sheet_url or ""
    try:
        source_name, dataframes, active_sheet = await asyncio.wait_for(
            asyncio.to_thread(
                load_google_sheet_to_dataframes,
                settings=settings,
                sheet_url_or_id=sheet_input,
                preferred_worksheet=payload.worksheet_name,
            ),
            timeout=120,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Google Sheet loading timed out. Check sharing and try again.") from exc

    dataset = store.add_dataset(
        session_id=session.session_id,
        source_name=source_name,
        dataframes=dataframes,
        active_sheet=active_sheet,
    )

    summary = summarize_dataframe(dataframes[active_sheet])
    return LoadGoogleSheetResponse(
        session_id=session.session_id,
        dataset_id=dataset.dataset_id,
        source_name=source_name,
        rows=summary["rows"],
        columns=summary["columns"],
        sheets=list(dataframes.keys()),
    )


@router.post("/ask", response_model=AskResponse, dependencies=[Depends(validate_api_key)])
async def ask_question(request: Request, payload: AskRequest) -> AskResponse:
    store = _get_store(request)
    settings = _get_settings(request)
    agent = _get_agent(request)

    try:
        resolved_dataset_id, dataframe = store.get_dataset(
            session_id=payload.session_id,
            dataset_id=payload.dataset_id,
            sheet_name=payload.sheet_name,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        answer, pandas_code = await asyncio.wait_for(
            asyncio.to_thread(agent.ask, payload.question, dataframe),
            timeout=max(settings.llm_timeout_seconds, 60),
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Query timed out. Try a shorter or more specific question.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Agent query failed")
        raise HTTPException(status_code=500, detail=f"Query execution failed: {exc}") from exc

    store.add_history(payload.session_id, payload.question, answer)

    return AskResponse(
        question=payload.question,
        answer=answer,
        pandas_code=pandas_code if payload.include_pandas_code else None,
        session_id=payload.session_id,
        dataset_id=resolved_dataset_id,
    )


@router.get("/history/{session_id}", response_model=ChatHistoryResponse, dependencies=[Depends(validate_api_key)])
async def get_history(request: Request, session_id: str) -> ChatHistoryResponse:
    store = _get_store(request)
    return ChatHistoryResponse(session_id=session_id, items=store.get_history(session_id))
