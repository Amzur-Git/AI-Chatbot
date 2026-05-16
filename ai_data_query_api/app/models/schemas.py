from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator


class UploadFileResponse(BaseModel):
    session_id: str
    dataset_id: str
    source_name: str
    rows: int
    columns: list[str]
    sheets: list[str]


class LoadGoogleSheetRequest(BaseModel):
    session_id: Optional[str] = None
    google_sheet_url: Optional[str] = None
    google_sheet_id: Optional[str] = None
    worksheet_name: Optional[str] = None

    @model_validator(mode="after")
    def validate_sheet_input(self) -> "LoadGoogleSheetRequest":
        if not self.google_sheet_url and not self.google_sheet_id:
            raise ValueError("Provide either google_sheet_url or google_sheet_id")
        return self


class LoadGoogleSheetResponse(BaseModel):
    session_id: str
    dataset_id: str
    source_name: str
    rows: int
    columns: list[str]
    sheets: list[str]


class AskRequest(BaseModel):
    session_id: str = Field(..., description="Session ID returned by upload/load endpoints")
    dataset_id: Optional[str] = Field(default=None, description="Dataset ID returned by upload/load endpoints")
    sheet_name: Optional[str] = Field(default=None, description="Worksheet name for multi-sheet datasets")
    question: str = Field(..., min_length=2)
    include_pandas_code: bool = True


class AskResponse(BaseModel):
    question: str
    answer: str
    pandas_code: Optional[str] = None
    session_id: str
    dataset_id: str


class ChatHistoryItem(BaseModel):
    question: str
    answer: str


class ChatHistoryResponse(BaseModel):
    session_id: str
    dataset_id: Optional[str] = None
    items: list[ChatHistoryItem]
