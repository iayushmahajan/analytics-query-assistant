import pytest

from app.api.schemas.query import QueryPlan
from app.services.metric_policy import prepare_query
from app.services.sql_validator import SQLValidationError


@pytest.mark.parametrize("metric,column", [
    ("retail_index", "value"),
    ("monthly_change", "monthly_change"),
    ("yearly_change", "yearly_change"),
    ("retail_volatility", "rolling_volatility"),
    ("retail_anomaly_score", "anomaly_score"),
])
def test_declared_metrics_use_the_single_eurostat_table(metric, column):
    plan = QueryPlan(
        status="ready",
        sql=f"SELECT period, {column} FROM retail_observations WHERE geo_code = 'DE'",
        metric=metric,
        interpretation="German retail metric",
        explanation="Read the requested Eurostat measure",
    )
    checked = prepare_query(plan)
    assert checked.source_tables == ["retail_observations"]
    assert "LIMIT 100" in checked.sql


def test_metric_policy_rejects_missing_or_removed_sources():
    plan = QueryPlan(
        status="ready",
        sql="SELECT COUNT(*) FROM query_history",
        metric="retail_index",
        interpretation="History",
        explanation="Invalid source",
    )
    with pytest.raises(SQLValidationError):
        prepare_query(plan)
