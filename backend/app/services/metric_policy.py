"""Require every generated query to use its declared Eurostat metric table."""

from app.api.schemas.query import QueryPlan
from app.constants.metrics import RETAIL_METRICS
from app.services.sql_validator import SQLValidationError, ValidatedSQL, validate_sql


def prepare_query(plan: QueryPlan) -> ValidatedSQL:
    checked = validate_sql(plan.sql or "")
    if plan.metric not in RETAIL_METRICS:
        raise SQLValidationError("The selected metric is not available.")
    metric = RETAIL_METRICS[plan.metric]
    if not set(metric.source_tables).issubset(checked.source_tables):
        raise SQLValidationError("The query is missing the source table required by its metric.")
    return checked
