import pytest
from sqlglot import exp, parse_one

from app.api.schemas.query import QueryPlan
from app.services.metric_policy import prepare_query


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT SUM(total_amount) FROM orders",
        "WITH o AS (SELECT * FROM orders WHERE status='pending' OR 1=1) SELECT SUM(total_amount) FROM o",
        "SELECT total_amount FROM orders UNION ALL SELECT total_amount FROM orders",
    ],
)
def test_revenue_population_enforced_on_every_source(sql):
    plan = QueryPlan(
        status="ready", sql=sql, metric="revenue", interpretation="Revenue", explanation="Revenue"
    )
    tree = parse_one(prepare_query(plan).sql, read="postgres")
    for table in tree.find_all(exp.Table):
        if table.name == "orders":
            assert table.parent.parent.args["where"].sql() == "WHERE status = 'completed'"


def test_order_count_preserves_explicit_status():
    plan = QueryPlan(
        status="ready",
        sql="SELECT COUNT(*) FROM orders WHERE status='pending'",
        metric="order_count",
        interpretation="Pending",
        explanation="Count",
    )
    assert "completed" not in prepare_query(plan).sql


def test_metric_rejects_wrong_source_population():
    from app.services.sql_validator import SQLValidationError

    plan = QueryPlan(
        status="ready",
        sql="SELECT COUNT(id) FROM customers",
        metric="revenue",
        interpretation="Revenue",
        explanation="Wrong source",
    )
    with pytest.raises(SQLValidationError):
        prepare_query(plan)
