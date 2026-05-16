from __future__ import annotations

from io import BytesIO

import pandas as pd
from fastapi import HTTPException
from google.auth.transport.requests import AuthorizedSession
from requests import Response

from app.config.settings import Settings
from app.utils.dataframe_utils import clean_dataframe
from app.utils.google_sheets import extract_sheet_id, get_google_credentials, open_spreadsheet


def _describe_google_sheet_error(exc: Exception) -> str:
    primary = str(exc).strip()
    if primary:
        return primary

    cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
    if cause is not None:
        cause_message = str(cause).strip()
        if cause_message:
            return cause_message

    return exc.__class__.__name__


def _is_office_file_google_sheet_error(exc: Exception) -> bool:
    message = _describe_google_sheet_error(exc).lower()
    return "must not be an office file" in message or "operation is not supported for this document" in message


def _extract_google_error_message(response: Response) -> str:
    try:
        payload = response.json()
        message = str(payload.get("error", {}).get("message") or "").strip()
        if message:
            return message
    except Exception:
        pass

    body = (response.text or "").strip()
    if body:
        return body

    return f"HTTP {response.status_code}"


def _load_office_file_from_drive(
    settings: Settings,
    file_id: str,
    preferred_worksheet: str | None = None,
) -> tuple[str, dict[str, pd.DataFrame], str]:
    credentials = get_google_credentials(settings)
    session = AuthorizedSession(credentials)

    metadata_resp = session.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        params={"fields": "id,name,mimeType"},
        timeout=60,
    )
    if metadata_resp.status_code >= 400:
        raise ValueError(f"Drive metadata request failed: {_extract_google_error_message(metadata_resp)}")

    metadata = metadata_resp.json()
    file_name = str(metadata.get("name") or file_id)

    media_resp = session.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        params={"alt": "media"},
        timeout=120,
    )
    if media_resp.status_code >= 400:
        raise ValueError(f"Drive file download failed: {_extract_google_error_message(media_resp)}")

    workbook = pd.read_excel(BytesIO(media_resp.content), sheet_name=None)
    if not workbook:
        raise ValueError("No worksheets found in Office spreadsheet")

    dataframes: dict[str, pd.DataFrame] = {}
    for sheet_name, df in workbook.items():
        dataframes[str(sheet_name)] = clean_dataframe(df)

    if preferred_worksheet and preferred_worksheet in dataframes:
        active_sheet = preferred_worksheet
    else:
        active_sheet = next(iter(dataframes.keys()))

    source_name = f"google_sheet:{file_name}"
    return source_name, dataframes, active_sheet


def load_google_sheet_to_dataframes(
    settings: Settings,
    sheet_url_or_id: str,
    preferred_worksheet: str | None = None,
) -> tuple[str, dict[str, pd.DataFrame], str]:
    sheet_id = extract_sheet_id(sheet_url_or_id)

    try:
        spreadsheet = open_spreadsheet(settings, sheet_id)
    except Exception as exc:
        if _is_office_file_google_sheet_error(exc):
            try:
                return _load_office_file_from_drive(settings, sheet_id, preferred_worksheet)
            except Exception as drive_exc:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Failed to open Google Sheet Office file. "
                        "Please convert the file to native Google Sheets or use CSV/XLSX upload mode. "
                        f"Details: {_describe_google_sheet_error(drive_exc)}"
                    ),
                ) from drive_exc

        raise HTTPException(status_code=400, detail=f"Failed to open Google Sheet: {_describe_google_sheet_error(exc)}") from exc

    worksheets = spreadsheet.worksheets()
    if not worksheets:
        raise HTTPException(status_code=400, detail="No worksheets found in Google Sheet")

    dataframes: dict[str, pd.DataFrame] = {}
    for worksheet in worksheets:
        values = worksheet.get_all_values()
        if not values:
            dataframes[worksheet.title] = pd.DataFrame()
            continue

        header = values[0]
        rows = values[1:] if len(values) > 1 else []
        df = pd.DataFrame(rows, columns=header)
        dataframes[worksheet.title] = clean_dataframe(df)

    if preferred_worksheet and preferred_worksheet in dataframes:
        active_sheet = preferred_worksheet
    else:
        active_sheet = worksheets[0].title

    source_name = f"google_sheet:{spreadsheet.title}"
    return source_name, dataframes, active_sheet
