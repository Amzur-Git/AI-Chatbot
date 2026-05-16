from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent
from langchain_openai import ChatOpenAI

from app.config.settings import Settings

logger = logging.getLogger(__name__)


class DataQueryAgentService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _build_llm(self) -> ChatOpenAI:
        if not self._settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required")

        return ChatOpenAI(
            api_key=self._settings.openai_api_key,
            base_url=self._settings.openai_base_url,
            model=self._settings.llm_model,
            temperature=self._settings.openai_temperature,
            timeout=self._settings.llm_timeout_seconds,
        )

    @staticmethod
    def _extract_pandas_code(intermediate_steps: list[Any]) -> str | None:
        extracted: list[str] = []
        for step in intermediate_steps:
            if not isinstance(step, tuple) or len(step) < 1:
                continue
            action = step[0]
            tool_name = str(getattr(action, "tool", ""))
            if "python" not in tool_name.lower():
                continue

            tool_input = getattr(action, "tool_input", None)
            if isinstance(tool_input, str):
                extracted.append(tool_input)
            elif isinstance(tool_input, dict):
                maybe_code = tool_input.get("query") or tool_input.get("code") or str(tool_input)
                extracted.append(str(maybe_code))
            elif tool_input is not None:
                extracted.append(str(tool_input))

        if not extracted:
            return None
        return "\n\n".join(extracted[-3:]).strip()

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _normalize_question_text(question: str) -> str:
        return re.sub(r"\s+", " ", question or "").strip()

    @staticmethod
    def _find_name_column(columns: list[str]) -> str | None:
        normalized = {col: col.strip().lower() for col in columns}
        for preferred in ("student name", "name", "student"):
            for original, lowered in normalized.items():
                if lowered == preferred:
                    return original
        for original, lowered in normalized.items():
            if "name" in lowered:
                return original
        return None

    @staticmethod
    def _find_target_column(question: str, columns: list[str], name_column: str | None) -> str | None:
        q = DataQueryAgentService._normalize_question_text(question).lower()
        if not q:
            return None

        match = re.search(r"what\s+is\s+(?:the\s+)?(.+?)\s+for", q)
        requested = match.group(1).strip().strip("? ") if match else q
        if not requested:
            return None

        direct_map = {col.lower(): col for col in columns}
        if requested in direct_map:
            candidate = direct_map[requested]
            if candidate != name_column:
                return candidate

        requested_tokens = [tok for tok in re.split(r"[^a-z0-9]+", requested) if tok]
        best_col: str | None = None
        best_score = 0
        for col in columns:
            if col == name_column:
                continue
            col_tokens = [tok for tok in re.split(r"[^a-z0-9]+", col.lower()) if tok]
            score = sum(1 for tok in requested_tokens if tok in col_tokens)
            if score > best_score:
                best_score = score
                best_col = col
        return best_col if best_score > 0 else None

    @staticmethod
    def _extract_person_name(question: str) -> str | None:
        normalized_question = DataQueryAgentService._normalize_question_text(question)
        patterns = [
            r"name\s*(?:is|=)\s*([a-zA-Z][a-zA-Z .'-]*)",
            r"student\s*(?:is|=)\s*([a-zA-Z][a-zA-Z .'-]*)",
            r"student\s+named\s+([a-zA-Z][a-zA-Z .'-]*)",
            r"for\s+student\s+(?:named\s+)?([a-zA-Z][a-zA-Z .'-]*)",
            r"(?:for|of)\s+([a-zA-Z][a-zA-Z .'-]*)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized_question, flags=re.IGNORECASE)
            if match:
                candidate = match.group(1).strip().strip("? ")
                candidate = re.sub(r"^named\s+", "", candidate, flags=re.IGNORECASE)
                candidate = re.sub(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$", "", candidate)
                return candidate.strip()
        return None

    def _try_exact_name_lookup(self, question: str, dataframe: pd.DataFrame) -> str | None:
        if dataframe.empty:
            return None

        name_column = self._find_name_column(list(dataframe.columns))
        person_name = self._extract_person_name(question)
        if not name_column or not person_name:
            return None

        target_column = self._find_target_column(question, list(dataframe.columns), name_column)
        if not target_column:
            return None

        normalized_target = person_name.casefold()
        name_series = dataframe[name_column].astype(str).str.strip()
        exact_mask = name_series.str.casefold() == normalized_target
        exact_rows = dataframe[exact_mask]

        if not exact_rows.empty:
            value = self._normalize_text(exact_rows.iloc[0][target_column])
            return value or f"{target_column} is empty for {person_name}."

        contains_mask = name_series.str.casefold().str.contains(re.escape(normalized_target), regex=True)
        contains_rows = dataframe[contains_mask]
        if len(contains_rows) == 1:
            value = self._normalize_text(contains_rows.iloc[0][target_column])
            return value or f"{target_column} is empty for {person_name}."

        available = [
            self._normalize_text(value)
            for value in dataframe[name_column].dropna().astype(str).tolist()
            if self._normalize_text(value)
        ]
        unique_available: list[str] = []
        for name in available:
            if name not in unique_available:
                unique_available.append(name)

        all_names = ", ".join(unique_available)
        if all_names:
            return (
                f"No exact match found for '{person_name}' in column '{name_column}'. "
                f"Available names ({len(unique_available)}): {all_names}."
            )
        return f"No exact match found for '{person_name}' in column '{name_column}'."

    def ask(self, question: str, dataframe: pd.DataFrame) -> tuple[str, str | None]:
        deterministic_answer = self._try_exact_name_lookup(question, dataframe)
        if deterministic_answer:
            return deterministic_answer, None

        llm = self._build_llm()

        prefix = (
            "You are an enterprise data analyst. "
            "Answer using the dataframe only. "
            "If data is missing, state it clearly. "
            "Prefer concise, business-friendly answers."
        )

        agent = create_pandas_dataframe_agent(
            llm,
            dataframe,
            agent_type="tool-calling",
            verbose=False,
            return_intermediate_steps=True,
            allow_dangerous_code=True,
            include_df_in_prompt=True,
            number_of_head_rows=5,
            prefix=prefix,
        )

        result = agent.invoke({"input": question})
        answer = str(result.get("output", "")).strip() or "No answer generated."
        pandas_code = self._extract_pandas_code(result.get("intermediate_steps", []))
        return answer, pandas_code
