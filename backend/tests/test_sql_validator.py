import pytest
from sqlglot import parse_one

from app.services.sql_validator import SQLValidationError, validate_sql


@pytest.mark.parametrize("sql", [
    "SELECT * FROM retail_lines",
    "SELECT SUM(quantity * unit_price) FROM retail_lines",
    "SELECT country, SUM(quantity) FROM retail_lines WHERE is_sale GROUP BY country",
    "SELECT * FROM retail_lines WHERE EXISTS(SELECT 1 FROM retail_lines)",
    "WITH x AS (SELECT * FROM retail_lines) SELECT * FROM x",
    'SELECT * FROM "retail_lines"',
    "SELECT * FROM public.retail_lines -- safe comment",
    "SELECT * FROM retail_lines WHERE description = 'Drop earrings'",
    "SELECT 'limit 1' FROM retail_lines",
    "SELECT id FROM retail_lines UNION SELECT id FROM retail_lines",
])
def test_safe_analytics_have_outer_limit(sql):
    validated = validate_sql(sql)
    assert int(parse_one(validated.sql, read="postgres").args["limit"].expression.this) <= 100


@pytest.mark.parametrize("sql", [
    "DELETE FROM retail_lines",
    "SELECT * INTO stolen FROM retail_lines",
    "SELECT * FROM retail_lines; SELECT * FROM retail_lines",
    "BEGIN",
    "SELECT * FROM query_history",
    "SELECT * FROM orders",
    "SELECT * FROM retail_lines, query_history",
    'SELECT * FROM retail_lines r JOIN "query_history" h ON true',
    "WITH x AS (SELECT * FROM query_history) SELECT * FROM x",
    "SELECT * FROM private.retail_lines",
    "SELECT * FROM pg_catalog.pg_class",
    "SELECT * FROM retail_lines UNION SELECT * FROM query_history",
    "SELECT * FROM retail_lines WHERE EXISTS(SELECT 1 FROM query_history)",
    "SELECT pg_sleep(1) FROM retail_lines",
    "SELECT set_config('search_path','x',false) FROM retail_lines",
    "SELECT public.count(*) FROM retail_lines",
    "SELECT * FROM retail_lines FOR SHARE",
    "WITH RECURSIVE x AS (SELECT * FROM retail_lines) SELECT * FROM x",
    "SELECT CAST('retail_lines' AS regclass) FROM retail_lines",
    "SELECT * FROM retail_lines LIMIT (SELECT 1)",
    "WITH x AS (DELETE FROM retail_lines RETURNING *) SELECT * FROM x",
])
def test_reject_unsafe_classes(sql):
    with pytest.raises(SQLValidationError):
        validate_sql(sql)


def test_cap_and_cte_shadowing():
    assert "LIMIT 100" in validate_sql("SELECT * FROM retail_lines LIMIT 9999").sql
    assert "LIMIT 5" in validate_sql("SELECT * FROM retail_lines LIMIT 5").sql
    with pytest.raises(SQLValidationError):
        validate_sql("WITH retail_lines AS (SELECT * FROM query_history) SELECT * FROM retail_lines")
