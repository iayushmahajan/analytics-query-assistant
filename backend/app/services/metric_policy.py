"""Enforce the canonical sale-line population before analytical SQL executes."""

from sqlglot import exp, parse_one
from sqlglot.optimizer.scope import traverse_scope

from app.api.schemas.query import QueryPlan
from app.constants.metrics import RETAIL_METRICS
from app.services.sql_validator import SQLValidationError, ValidatedSQL, validate_sql


def prepare_query(plan: QueryPlan) -> ValidatedSQL:
    checked = validate_sql(plan.sql or "")
    if plan.metric not in RETAIL_METRICS:
        raise SQLValidationError("The selected metric is not available.")
    metric = RETAIL_METRICS[plan.metric]
    if not set(metric.source_tables).issubset(checked.source_tables):
        raise SQLValidationError("The query is missing source tables required by its selected metric.")
    if metric.included_statuses != ["sale"]:
        return checked
    tree = parse_one(checked.sql, read="postgres")
    # Replace actual retail_lines sources, never a CTE with that name.
    for scope in list(traverse_scope(tree)):
        for alias, (_, source) in scope.selected_sources.items():
            if not isinstance(source, exp.Table) or source.name != "retail_lines":
                continue
            for column in scope.columns:
                if column.table == alias and column.db == source.db:
                    column.set("db", None)
                    column.set("catalog", None)
            population = (
                exp.select("*")
                .from_(exp.Table(this=exp.to_identifier("retail_lines"), db=exp.to_identifier("public")))
                .where(exp.EQ(this=exp.column("is_sale"), expression=exp.true()))
                .subquery(alias=alias)
            )
            source.replace(population)
    return validate_sql(tree.sql(dialect="postgres"))
