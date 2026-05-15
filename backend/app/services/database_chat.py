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

_SENSITIVE_COLUMN_TOKENS = {
    "password",
    "password_hash",
    "secret",
    "token",
    "api_key",
    "private_key",
    "credential",
}

_RELATIONSHIP_HINTS = (
    "users.id -> chat_messages.user_id, "
    "users.id -> attachments.user_id, "
    "users.id -> image_generations.user_id"
)

_METADATA_ALLOWED_TABLES = {
    ("information_schema", "columns"),
    ("information_schema", "tables"),
}


def _parse_allowed_schemas() -> set[str]:
    values = [item.strip().lower() for item in (settings.db_chat_allowed_schemas or "").split(",") if item.strip()]
    return set(values or ["public"])


def _parse_allowed_tables() -> set[str]:
    values = [item.strip().lower() for item in (settings.db_chat_allowed_tables or "").split(",") if item.strip()]
    return set(values)


def _contains_sensitive_token(text_value: str) -> bool:
    normalized = (text_value or "").lower()
    return any(token in normalized for token in _SENSITIVE_COLUMN_TOKENS)


def _table_alias_map() -> dict[str, str]:
    allowed_tables = _parse_allowed_tables()
    aliases: dict[str, str] = {}
    for table_name in allowed_tables:
        cleaned = table_name.strip().lower()
        if not cleaned:
            continue

        compact = cleaned.replace("_", "")
        aliases[cleaned] = cleaned
        aliases[compact] = cleaned

        if cleaned.endswith("s") and len(cleaned) > 1:
            singular = cleaned[:-1]
            aliases[singular] = cleaned
            aliases[singular.replace("_", "")] = cleaned

    return aliases


def _guess_table_name_from_question(question: str) -> str | None:
    q = (question or "").strip().lower()
    if not q:
        return None

    aliases = _table_alias_map()
    if not aliases:
        return None

    compact_q = re.sub(r"[^a-z0-9_]", "", q)
    for alias, mapped in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        normalized_alias = alias.replace("_", "")
        if normalized_alias and normalized_alias in compact_q:
            return mapped

    return None


def _metadata_sql_from_question(question: str) -> str | None:
    q = (question or "").strip().lower()
    if not q:
        return None

    table_name = _guess_table_name_from_question(q)

    # Table list/count questions.
    if "table" in q and not table_name:
        if re.search(r"\b(how many|count|number of)\b", q):
            return (
                "SELECT COUNT(*) AS table_count "
                "FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            )
        if re.search(r"\b(list|show|what|which)\b", q):
            return (
                "SELECT table_name "
                "FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
                "ORDER BY table_name"
            )

    if not table_name:
        return None

    # Column count/list questions for a specific table.
    if "column" in q:
        if re.search(r"\b(how many|count|number of)\b", q):
            return (
                "SELECT COUNT(*) AS column_count "
                "FROM information_schema.columns "
                f"WHERE table_schema = 'public' AND table_name = '{table_name}'"
            )

        if re.search(r"\b(list|show|what|which|all)\b", q):
            return (
                "SELECT column_name, data_type "
                "FROM information_schema.columns "
                f"WHERE table_schema = 'public' AND table_name = '{table_name}' "
                "ORDER BY ordinal_position"
            )

    return None


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
    body_lines: list[str] = []
    for index, row in enumerate(limited_rows, start=1):
        body_lines.append(f"Row {index}:")
        for key, value in row.items():
            body_lines.append(f"- {key}: {_serialize_cell(value)}")
        body_lines.append("")

    output = "\n".join(body_lines).strip()
    if len(rows) > max_rows:
        output += f"\n\nShowing first {max_rows} rows out of {len(rows)} total rows."
    return output


async def _build_schema_summary(db: AsyncSession) -> str:
    allowed_schemas = _parse_allowed_schemas()
    allowed_tables = _parse_allowed_tables()

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
        schema_name = str(item["table_schema"]).lower()
        table_name = str(item["table_name"]).lower()
        column_name = str(item["column_name"])
        if allowed_tables and table_name not in allowed_tables:
            continue
        if _contains_sensitive_token(column_name):
            continue

        key = (schema_name, table_name)
        grouped[key].append(f"{column_name} ({item['data_type']})")

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
        if schema_name in allowed_schemas and (not allowed_tables or table_name in allowed_tables):
            continue
        if (schema_name, table_name) in _METADATA_ALLOWED_TABLES:
            continue
        return False
    return True


def _references_sensitive_columns(sql: str) -> bool:
    # Conservative guard: block if SQL references obvious secret-like tokens.
    return _contains_sensitive_token(sql)


def _ensure_safe_limit(sql: str, max_limit: int = 100) -> str:
    normalized = (sql or "").strip().rstrip(";")
    if not normalized:
        return normalized

    limit_match = re.search(r"\blimit\s+(\d+)\b", normalized, re.IGNORECASE)
    if not limit_match:
        return f"{normalized} LIMIT {max_limit}"

    try:
        current_limit = int(limit_match.group(1))
    except ValueError:
        return f"{normalized} LIMIT {max_limit}"

    if current_limit <= max_limit:
        return normalized

    return re.sub(
        r"\blimit\s+\d+\b",
        f"LIMIT {max_limit}",
        normalized,
        flags=re.IGNORECASE,
        count=1,
    )


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

    metadata_sql = _metadata_sql_from_question(user_question)
    if metadata_sql:
        sql = _ensure_safe_limit(metadata_sql, max_limit=100)
        query_result = await db.execute(text(sql))
        mapped_rows = [dict(row) for row in query_result.mappings().all()]
        table = _format_rows_as_markdown(mapped_rows, max_rows=settings.db_chat_max_rows)
        return f"[Database Chat]\nHere is the database result for your question.\n\nSQL Used:\n```sql\n{sql}\n```\n\nResult:\n{table}"

    schema_summary = await _build_schema_summary(db)

    planner_prompt = (
        "You are an AI Database Assistant SQL planner for PostgreSQL. "
        "Decide if the user question should be answered by querying the database. "
        "Return strict JSON only with keys: use_database (boolean), sql (string), rationale (string). "
        "Rules: generate read-only SQL only (SELECT/CTE). Never use INSERT/UPDATE/DELETE/DDL. "
        "Use JOINs automatically when needed. "
        "Handle metadata questions too (e.g., list tables, count columns in a table). "
        "Never select password_hash or any secret/token/api key columns. "
        "For large/non-aggregate result sets, include LIMIT 100. "
        "If question is not database-related, return use_database=false and sql=''."
    )

    planning_response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": planner_prompt},
            {"role": "system", "content": f"Database schema:\n{schema_summary}"},
            {"role": "system", "content": f"Known relationships:\n{_RELATIONSHIP_HINTS}"},
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
    if _references_sensitive_columns(sql):
        return "I can't access password or secret fields. Please ask for non-sensitive data."

    sql = _ensure_safe_limit(sql, max_limit=100)
    if not _is_sql_allowed_by_allowlist(sql):
        return "This query targets tables outside the allowed database scope."

    query_result = await db.execute(text(sql))
    mapped_rows = [dict(row) for row in query_result.mappings().all()]
    table = _format_rows_as_markdown(mapped_rows, max_rows=settings.db_chat_max_rows)

    answer_prompt = (
        "You are a helpful data analyst. Explain SQL result in simple English. "
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
