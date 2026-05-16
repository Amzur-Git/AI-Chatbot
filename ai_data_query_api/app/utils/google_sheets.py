from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

import gspread
from dotenv import dotenv_values
from google.oauth2 import service_account
from gspread.spreadsheet import Spreadsheet

from app.config.settings import Settings

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _read_env_key_from_file(env_file: Path, key: str) -> str:
    if not env_file.exists():
        return ""

    prefix = f"{key}="
    for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith(prefix):
            return stripped[len(prefix):].strip().strip('"').strip("'")
    return ""


def _resolve_json_credential_path(path_value: str) -> Optional[Path]:
    candidate = Path(path_value)

    if candidate.is_file():
        return candidate

    if candidate.is_dir():
        json_files = sorted(candidate.glob("*.json"))
        if json_files:
            return json_files[0]

    return None


def _resolve_google_credential_values(settings: Settings) -> tuple[str, str]:
    json_or_path = (settings.google_service_account_json or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or "").strip()
    credentials_file = (settings.google_service_account_file or os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE") or "").strip()

    if not json_or_path and not credentials_file:
        backend_env_file = Path(__file__).resolve().parents[3] / "backend" / ".env"
        if backend_env_file.exists():
            env_values = dotenv_values(backend_env_file)
            json_or_path = str(env_values.get("GOOGLE_SERVICE_ACCOUNT_JSON") or "").strip()
            credentials_file = str(env_values.get("GOOGLE_SERVICE_ACCOUNT_FILE") or "").strip()

            # Fallback for edge cases where dotenv misses Windows-style paths.
            if not json_or_path:
                json_or_path = _read_env_key_from_file(backend_env_file, "GOOGLE_SERVICE_ACCOUNT_JSON")
            if not credentials_file:
                credentials_file = _read_env_key_from_file(backend_env_file, "GOOGLE_SERVICE_ACCOUNT_FILE")

    return json_or_path, credentials_file


def get_google_credentials(settings: Settings) -> service_account.Credentials:
    json_or_path, credentials_file = _resolve_google_credential_values(settings)

    if json_or_path:
        if json_or_path.startswith("{"):
            credentials = json.loads(json_or_path)
            return service_account.Credentials.from_service_account_info(credentials, scopes=GOOGLE_SCOPES)

        json_path = _resolve_json_credential_path(json_or_path)
        if json_path is not None:
            return service_account.Credentials.from_service_account_file(str(json_path), scopes=GOOGLE_SCOPES)

    if credentials_file:
        json_path = _resolve_json_credential_path(credentials_file)
        if json_path is not None:
            return service_account.Credentials.from_service_account_file(str(json_path), scopes=GOOGLE_SCOPES)

        raise ValueError("GOOGLE_SERVICE_ACCOUNT_FILE is set but does not point to a readable JSON credential file")

    if json_or_path:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON is set but is neither valid JSON nor a readable JSON credential file")

    raise ValueError("Set GOOGLE_SERVICE_ACCOUNT_FILE or GOOGLE_SERVICE_ACCOUNT_JSON in environment")


def extract_sheet_id(url_or_id: str) -> str:
    candidate = (url_or_id or "").strip()
    if not candidate:
        raise ValueError("Google Sheet URL or ID is required")

    if "docs.google.com" not in candidate:
        return candidate

    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", candidate)
    if not match:
        raise ValueError("Could not extract Google Sheet ID from URL")
    return match.group(1)


def get_gspread_client(settings: Settings) -> gspread.Client:
    credentials = get_google_credentials(settings)
    return gspread.authorize(credentials)


def open_spreadsheet(settings: Settings, sheet_id: str) -> Spreadsheet:
    client = get_gspread_client(settings)
    return client.open_by_key(sheet_id)
