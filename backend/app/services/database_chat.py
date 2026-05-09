from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings

_BLOCKED_SQL_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "grant",
    "revoke",
    "comment",
    "copy",
    "call",
    "execute",
    "do",
    "merge",
}


def _parse_allowed_schemas() -> set[str]:
    values = [item.strip().lower() for item in (settings.db_chat_allowed_schemas or "").split(",") if item.strip()]
    return set(values or ["public"])


def _parse_allowed_tables() -> set[str]:
    values = [item.strip().lower() for item in (settings.db_chat_allowed_tables or "").split(",") if item.strip()]
    return set(values)


def _clean_json_payload(raw: str) -> dict[str, Any] | None:
    text_payload = (raw or "").strip()
    if not text_payload:
        return None

    if text_payload.startswith("```"):
        text_payload = re.sub(r"^```(?:json)?\s*", "", text_payload)
        text_payload = re.sub(r"\s*```$", "", text_payload)

    try:
        parsed = json.loads(text_payload)
    except Exception:
        return None

    return parsed if isinstance(parsed, dict) else None


def _is_read_only_sql(sql: str) -> bool:
    candidate = (sql or "").strip().rstrip(";").strip()
    if not candidate:
        return False

    lowered = candidate.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return False

    if ";" in candidate:
        return False

    keyword_pattern = r"\b(" + "|".join(sorted(_BLOCKED_SQL_KEYWORDS)) + r")\b"
    if re.search(keyword_pattern, lowered):
        return False

    return True


def _serialize_cell(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _format_rows_as_markdown(rows: list[dict[str, Any]], max_rows: int) -> str:
    if not rows:
        return "No rows matched your query."

    limited_rows = rows[:max_rows]
    columns = list(limited_rows[0].keys())

    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join(["---"] * len(columns)) + " |"
    body_lines: list[str] = []
    for row in limited_rows:
        body_lines.append("| " + " | ".join(_serialize_cell(row.get(col)) for col in columns) + " |")

    output = "\n".join([header, divider, *body_lines])
    if len(rows) > max_rows:
        output += f"\n\nShowing first {max_rows} rows out of {len(rows)} total rows."
    return output


async def _build_schema_summary(db: AsyncSession) -> str:
    allowed_schemas = _parse_allowed_schemas()

    result = await db.execute(
        text(
            """
            SELECT table_schema, table_name, column_name, data_type, ordinal_position
            FROM information_schema.columns
            WHERE table_schema = ANY(:schemas)
            ORDER BY table_schema, table_name, ordinal_position
            """
        ),
        {"schemas": list(allowed_schemas)},
    )
    rows = result.mappings().all()
    if not rows:
        return "No visible tables found."

    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for item in rows:
        key = (str(item["table_schema"]), str(item["table_name"]))
        grouped[key].append(f"{item['column_name']} ({item['data_type']})")

    lines: list[str] = []
    table_items = sorted(grouped.items())[: settings.db_chat_schema_max_tables]
    for (schema_name, table_name), columns in table_items:
        visible_columns = columns[: settings.db_chat_schema_max_columns_per_table]
        line = f"- {schema_name}.{table_name}: " + ", ".join(visible_columns)
        if len(columns) > len(visible_columns):
            line += ", ..."
        lines.append(line)

    return "\n".join(lines)


def _extract_referenced_tables(sql: str) -> set[tuple[str, str]]:
    candidate = (sql or "").strip()
    if not candidate:
        return set()

    # Basic parser for FROM/JOIN targets in generated read-only SQL.
    pattern = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][\w\.\"]*)", re.IGNORECASE)
    referenced: set[tuple[str, str]] = set()
    for match in pattern.finditer(candidate):
        raw_name = match.group(1).strip().strip('"')
        parts = [item.strip().strip('"') for item in raw_name.split(".") if item.strip()]
        if len(parts) == 1:
            referenced.add(("public", parts[0].lower()))
        elif len(parts) >= 2:
            referenced.add((parts[-2].lower(), parts[-1].lower()))
    return referenced


def _is_sql_allowed_by_allowlist(sql: str) -> bool:
    allowed_schemas = _parse_allowed_schemas()
    allowed_tables = _parse_allowed_tables()
    referenced = _extract_referenced_tables(sql)
    if not referenced:
        return False

    for schema_name, table_name in referenced:
        if schema_name not in allowed_schemas:
            return False
        if allowed_tables and table_name not in allowed_tables:
            return False
    return True


async def try_database_chat_answer(
    *,
    question: str,
    db: AsyncSession,
    client,
    model_name: str,
) -> str | None:
    user_question = (question or "").strip()
    if not user_question:
        return None

    schema_summary = await _build_schema_summary(db)

    planner_prompt = (
        "You are a SQL planner for PostgreSQL. Decide if the user question should be answered by querying the database. "
        "Return strict JSON only with keys: use_database (boolean), sql (string), rationale (string). "
        "Rules: generate read-only SQL only (SELECT/CTE). Never use INSERT/UPDATE/DELETE/DDL. "
        "Prefer explicit table names and include LIMIT 50 unless aggregation naturally returns one row. "
        "If question is not database-related, return use_database=false and sql=''."
    )

    planning_response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": planner_prompt},
            {"role": "system", "content": f"Database schema:\n{schema_summary}"},
            {"role": "user", "content": user_question},
        ],
        temperature=0.0,
        max_tokens=350,
    )

    raw_plan = planning_response.choices[0].message.content or ""
    plan = _clean_json_payload(raw_plan)
    if not plan or not bool(plan.get("use_database")):
        return None

    sql = str(plan.get("sql") or "").strip()
    if not _is_read_only_sql(sql):
        return "I can only run safe read-only SQL queries. Please rephrase your question."
    if not _is_sql_allowed_by_allowlist(sql):
        return "This query targets tables outside the allowed database scope."

    query_result = await db.execute(text(sql))
    mapped_rows = [dict(row) for row in query_result.mappings().all()]
    table = _format_rows_as_markdown(mapped_rows, max_rows=settings.db_chat_max_rows)

    answer_prompt = (
        "You are a helpful data analyst. Explain SQL result succinctly and clearly. "
        "Use only the provided SQL output. If no rows, say no matching data was found."
    )

    answer_response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": answer_prompt},
            {"role": "user", "content": f"Question: {user_question}\nSQL: {sql}\nResult:\n{table}"},
        ],
        temperature=0.1,
        max_tokens=500,
    )

    explanation = (answer_response.choices[0].message.content or "").strip()
    if not explanation:
        explanation = "Here are the query results."

    return f"[Database Chat]\n{explanation}\n\nSQL Used:\n```sql\n{sql}\n```\n\nResult:\n{table}"
