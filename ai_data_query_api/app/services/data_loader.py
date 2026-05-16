from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pandas as pd
from fastapi import HTTPException, UploadFile

from app.utils.dataframe_utils import clean_dataframe

_ALLOWED_EXTENSIONS = {".csv", ".xlsx"}


def _parse_uploaded_file_to_dataframes(
    target_file: Path,
    extension: str,
    original_filename: str,
) -> tuple[str, dict[str, pd.DataFrame], str]:
    if extension == ".csv":
        df = pd.read_csv(target_file, low_memory=False)
        df = clean_dataframe(df)
        return original_filename, {"Sheet1": df}, "Sheet1"

    sheets = pd.read_excel(target_file, sheet_name=None, engine="openpyxl")
    if not sheets:
        raise HTTPException(status_code=400, detail="No sheets found in Excel file")

    cleaned = {sheet_name: clean_dataframe(df) for sheet_name, df in sheets.items()}
    first_sheet = next(iter(cleaned.keys()))
    return original_filename, cleaned, first_sheet


async def load_file_to_dataframes(
    file: UploadFile,
    upload_dir: Path,
    max_upload_mb: int,
) -> tuple[str, dict[str, pd.DataFrame], str]:
    filename = file.filename or "uploaded_file"
    extension = Path(filename).suffix.lower()
    if extension not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .csv and .xlsx files are supported")

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > max_upload_mb:
        raise HTTPException(status_code=413, detail=f"File exceeds {max_upload_mb} MB limit")

    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4()}_{filename}"
    target_file = upload_dir / stored_name
    target_file.write_bytes(content)

    try:
        return await asyncio.to_thread(_parse_uploaded_file_to_dataframes, target_file, extension, filename)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {exc}") from exc
