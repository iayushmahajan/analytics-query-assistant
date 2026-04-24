import re

from app.constants.allowed_tables import ALLOWED_TABLES
from app.core.config import settings


BLOCKED_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "grant",
    "revoke",
    "merge",
    "copy",
}


class SQLValidationError(Exception):
    pass


def normalize_sql(sql: str) -> str:
    return sql.strip().rstrip(";")


def ensure_not_empty(sql: str) -> None:
    if not sql.strip():
        raise SQLValidationError("Generated SQL is empty.")


def ensure_single_statement(sql: str) -> None:
    statement_count = len([part for part in sql.split(";") if part.strip()])
    if statement_count > 1:
        raise SQLValidationError("Multiple SQL statements are not allowed.")


def ensure_select_only(sql: str) -> None:
    normalized = normalize_sql(sql).lstrip().lower()
    if not normalized.startswith("select"):
        raise SQLValidationError("Only SELECT queries are allowed.")


def ensure_no_blocked_keywords(sql: str) -> None:
    lowered = sql.lower()
    for keyword in BLOCKED_KEYWORDS:
        if re.search(rf"\b{keyword}\b", lowered):
            raise SQLValidationError(f"Blocked SQL keyword detected: {keyword.upper()}.")


def extract_table_names(sql: str) -> set[str]:
    pattern = r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)"
    matches = re.findall(pattern, sql, flags=re.IGNORECASE)
    return {match.lower() for match in matches}


def ensure_allowed_tables_only(sql: str) -> None:
    table_names = extract_table_names(sql)

    if not table_names:
        raise SQLValidationError("No valid table references were found in the SQL query.")

    invalid_tables = sorted(table_names - ALLOWED_TABLES)
    if invalid_tables:
        raise SQLValidationError(
            f"SQL references tables outside the allowed schema: {', '.join(invalid_tables)}."
        )


def has_limit_clause(sql: str) -> bool:
    return re.search(r"\blimit\s+\d+\b", sql, flags=re.IGNORECASE) is not None


def enforce_row_limit(sql: str) -> str:
    normalized = normalize_sql(sql)

    limit_match = re.search(r"\blimit\s+(\d+)\b", normalized, flags=re.IGNORECASE)
    if limit_match:
        current_limit = int(limit_match.group(1))
        if current_limit > settings.MAX_SQL_ROWS:
            normalized = re.sub(
                r"\blimit\s+\d+\b",
                f"LIMIT {settings.MAX_SQL_ROWS}",
                normalized,
                count=1,
                flags=re.IGNORECASE,
            )
        return normalized

    return f"{normalized}\nLIMIT {settings.MAX_SQL_ROWS}"


def validate_and_sanitize_sql(sql: str) -> str:
    ensure_not_empty(sql)
    ensure_single_statement(sql)
    ensure_select_only(sql)
    ensure_no_blocked_keywords(sql)
    ensure_allowed_tables_only(sql)

    safe_sql = enforce_row_limit(sql)
    return safe_sql