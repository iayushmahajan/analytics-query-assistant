"""Fail-closed PostgreSQL AST policy. Database permissions are the final boundary."""

from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.scope import Scope, traverse_scope

from app.constants.allowed_tables import ALLOWED_TABLES
from app.core.config import settings

SAFE_FUNCTIONS = {
    "AND",
    "OR",
    "EXISTS",
    "SUM",
    "COUNT",
    "AVG",
    "MIN",
    "MAX",
    "ROUND",
    "ABS",
    "CEIL",
    "FLOOR",
    "COALESCE",
    "NULLIF",
    "CAST",
    "EXTRACT",
    "TIMESTAMP_TRUNC",
    "DATE_TRUNC",
    "CURRENT_DATE",
    "CURRENT_TIMESTAMP",
    "LOWER",
    "UPPER",
    "TRIM",
    "LENGTH",
    "SUBSTRING",
    "CONCAT",
    "CASE",
    "IF",
    "ROW_NUMBER",
    "RANK",
    "DENSE_RANK",
    "LAG",
    "LEAD",
    "FIRST_VALUE",
    "LAST_VALUE",
    "GREATEST",
    "LEAST",
    "STDDEV",
    "STDDEV_POP",
    "STDDEV_SAMP",
    "VARIANCE",
    "VAR_POP",
}
FORBIDDEN_NODES = {
    "Insert",
    "Update",
    "Delete",
    "Drop",
    "Alter",
    "Create",
    "TruncateTable",
    "Merge",
    "Copy",
    "Command",
    "Transaction",
    "Commit",
    "Rollback",
    "Into",
    "Lock",
    "Set",
    "Use",
    "Grant",
    "Revoke",
    "Execute",
    "Parameter",
    "Placeholder",
    "TableSample",
    "Pivot",
    "Unpivot",
    "Lateral",
}


class SQLValidationError(Exception):
    pass


@dataclass(frozen=True)
class ValidatedSQL:
    sql: str
    source_tables: list[str]
    contains_customer_data: bool


def validate_sql(sql: str) -> ValidatedSQL:
    if not sql.strip() or len(sql) > 20000:
        raise SQLValidationError("SQL must be nonempty and within the size limit.")
    try:
        statements = [x for x in sqlglot.parse(sql, read="postgres") if x is not None]
        if len(statements) != 1 or not isinstance(
            statements[0], (exp.Select, exp.Union, exp.Intersect, exp.Except)
        ):
            raise SQLValidationError("Only one read-only analytical query is allowed.")
        tree = statements[0]
        if sum(1 for _ in tree.walk()) > 1500:
            raise SQLValidationError("Query is too complex.")
        for node in tree.walk():
            if type(node).__name__ in FORBIDDEN_NODES:
                raise SQLValidationError("This SQL operation is not permitted.")
            if isinstance(node, exp.With) and node.args.get("recursive"):
                raise SQLValidationError("Recursive queries are not permitted.")
            if isinstance(node, exp.Func):
                if isinstance(node, exp.Anonymous) or node.sql_name() not in SAFE_FUNCTIONS:
                    raise SQLValidationError("Query uses a function outside the analytics allowlist.")
                if isinstance(node.parent, exp.Dot):
                    raise SQLValidationError("Qualified functions are not permitted.")
            if isinstance(node, exp.Cast):
                if node.to.sql(dialect="postgres").upper() not in {
                    "DATE",
                    "TIMESTAMP",
                    "TIMESTAMPTZ",
                    "TEXT",
                    "INT",
                    "BIGINT",
                    "DOUBLE PRECISION",
                    "FLOAT",
                    "DECIMAL",
                    "BOOLEAN",
                }:
                    raise SQLValidationError("This cast type is not permitted.")
        tables = set()
        for scope in traverse_scope(tree):
            for _, source in scope.selected_sources.values():
                if isinstance(source, Scope):
                    continue
                if not isinstance(source, exp.Table) or not isinstance(source.this, exp.Identifier):
                    raise SQLValidationError("Only approved business tables may be queried.")
                if source.catalog or source.db not in ("", "public") or source.name not in ALLOWED_TABLES:
                    raise SQLValidationError("Query references an unauthorized table or schema.")
                tables.add(source.name)
        if not tables:
            raise SQLValidationError("An approved business table is required.")
        limit = tree.args.get("limit")
        value = limit.expression if isinstance(limit, exp.Limit) else None
        if value is not None and (not isinstance(value, exp.Literal) or not value.is_int):
            raise SQLValidationError("LIMIT must be a nonnegative integer.")
        cap = min(int(value.this), settings.MAX_SQL_ROWS) if value is not None else settings.MAX_SQL_ROWS
        if cap < 0:
            raise SQLValidationError("LIMIT must be nonnegative.")
        tree = tree.limit(cap)
        return ValidatedSQL(
                tree.sql(dialect="postgres", pretty=True, comments=False), sorted(tables), False
        )
    except (SqlglotError, ValueError, RecursionError) as exc:
        raise SQLValidationError("SQL could not be validated.") from exc


def validate_and_sanitize_sql(sql: str) -> str:
    return validate_sql(sql).sql
