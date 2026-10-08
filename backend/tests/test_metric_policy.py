import pytest
from sqlglot import exp, parse_one

from app.api.schemas.query import QueryPlan
from app.services.metric_policy import prepare_query
from app.services.sql_validator import SQLValidationError


@pytest.mark.parametrize("sql", [
    "SELECT SUM(quantity * unit_price) FROM retail_lines",
    "WITH x AS (SELECT * FROM retail_lines WHERE is_sale=false OR 1=1) SELECT SUM(quantity * unit_price) FROM x",
    "SELECT quantity FROM retail_lines UNION ALL SELECT quantity FROM retail_lines",
])
def test_sale_population_enforced_on_every_source(sql):
    plan = QueryPlan(status="ready", sql=sql, metric="retail_gross_sales",
                     interpretation="Gross sales", explanation="Sale value")
    tree = parse_one(prepare_query(plan).sql, read="postgres")
    sources = [table for table in tree.find_all(exp.Table) if table.name == "retail_lines"]
    assert sources
    for table in sources:
        assert table.parent.parent.args["where"].sql() == "WHERE is_sale = TRUE"


def test_removed_table_rejected():
    plan = QueryPlan(status="ready", sql="SELECT COUNT(*) FROM orders", metric="retail_invoices",
                     interpretation="Invoices", explanation="Count")
    with pytest.raises(SQLValidationError):
        prepare_query(plan)
