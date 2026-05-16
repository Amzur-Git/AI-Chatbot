from __future__ import annotations

from typing import Any

import pandas as pd


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned.columns = [str(col).strip() for col in cleaned.columns]
    cleaned = cleaned.where(pd.notnull(cleaned), None)
    return cleaned


def summarize_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "rows": int(df.shape[0]),
        "columns": [str(col) for col in df.columns.tolist()],
    }
