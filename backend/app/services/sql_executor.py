import time
from decimal import Decimal
from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session


class SQLExecutionError(Exception):
    pass


def serialize_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def execute_select_sql(db: Session, sql: str) -> dict:
    start = time.perf_counter()

    try:
        result = db.execute(text(sql))
    except Exception as exc:
        raise SQLExecutionError(f"SQL execution failed: {str(exc)}") from exc

    execution_time_ms = int((time.perf_counter() - start) * 1000)

    columns = list(result.keys())
    raw_rows = result.fetchall()

    rows = [
        [serialize_value(value) for value in row]
        for row in raw_rows
    ]

    return {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "execution_time_ms": execution_time_ms,
    }