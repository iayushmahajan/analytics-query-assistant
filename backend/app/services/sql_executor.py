import json
import math
import time
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.analytics_security import reader_is_restricted
from app.core.config import settings
from app.core.db import analytics_engine
from app.services.sql_validator import ValidatedSQL


class SQLExecutionError(Exception):
    def __init__(self, code: str = "execution_failed"):
        self.code = code
        super().__init__("The query timed out. Try a narrower question." if code == "query_timeout" else "The query could not be executed.")


def serialize_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError("Unsupported result type")


def execute_select_sql(query: ValidatedSQL) -> dict:
    start = time.perf_counter()
    try:
        with analytics_engine.connect() as connection:
            with connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                if not reader_is_restricted(connection):
                    raise ValueError("Analytics role is not restricted")
                connection.execute(text("SELECT set_config('statement_timeout', :timeout, true)"), {"timeout": str(settings.SQL_STATEMENT_TIMEOUT_MS)})
                connection.execute(text("SET LOCAL search_path = pg_catalog, public"))
                result = connection.execute(text(query.sql))
                columns = list(result.keys())
                if any(len(c) > 64 for c in columns) or len(columns) > 40 or len(set(columns)) != len(columns):
                    raise ValueError("Result needs at most 40 uniquely named columns")
                rows = [[serialize_value(v) for v in row] for row in result.fetchmany(settings.MAX_SQL_ROWS + 1)]
                if len(rows) > settings.MAX_SQL_ROWS:
                    raise ValueError("Result exceeded row limit")
                if len(json.dumps(rows).encode()) > settings.MAX_RESULT_BYTES:
                    raise ValueError("Result exceeded byte limit")
    except (SQLAlchemyError, ValueError, TypeError, OverflowError) as exc:
        code = "query_timeout" if getattr(getattr(exc, "orig", None), "pgcode", None) == "57014" else "execution_failed"
        raise SQLExecutionError(code) from exc
    return {"columns": columns, "rows": rows, "row_count": len(rows),
            "execution_time_ms": round((time.perf_counter() - start) * 1000),
            "possibly_truncated": len(rows) == settings.MAX_SQL_ROWS}
