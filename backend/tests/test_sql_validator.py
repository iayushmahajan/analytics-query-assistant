import pytest
from sqlglot import parse_one

from app.services.sql_validator import SQLValidationError, validate_sql


@pytest.mark.parametrize("sql", [
    "SELECT * FROM retail_observations",
    "SELECT AVG(value) FROM retail_observations",
    "SELECT geography, MAX(yearly_change) FROM retail_observations GROUP BY geography",
    "SELECT * FROM retail_observations WHERE EXISTS(SELECT 1 FROM retail_observations)",
    "WITH x AS (SELECT * FROM retail_observations) SELECT * FROM x",
    'SELECT * FROM "retail_observations"',
    "SELECT * FROM public.retail_observations -- safe comment",
    "SELECT * FROM retail_observations WHERE category = 'Automotive fuel'",
    "SELECT 'limit 1' FROM retail_observations",
    "SELECT period FROM retail_observations UNION SELECT period FROM retail_observations",
    "SELECT geography, LAG(value) OVER (PARTITION BY geo_code ORDER BY period) FROM retail_observations",
])
def test_safe_analytics_have_outer_limit(sql):
    validated = validate_sql(sql)
    assert int(parse_one(validated.sql, read="postgres").args["limit"].expression.this) <= 100


@pytest.mark.parametrize("sql", [
    "DELETE FROM retail_observations",
    "SELECT * INTO stolen FROM retail_observations",
    "SELECT * FROM retail_observations; SELECT * FROM retail_observations",
    "BEGIN",
    "SELECT * FROM query_history",
    "SELECT * FROM retail_lines",
    "SELECT * FROM retail_observations, query_history",
    'SELECT * FROM retail_observations r JOIN "query_history" h ON true',
    "WITH x AS (SELECT * FROM query_history) SELECT * FROM x",
    "SELECT * FROM private.retail_observations",
    "SELECT * FROM pg_catalog.pg_class",
    "SELECT * FROM retail_observations UNION SELECT * FROM query_history",
    "SELECT * FROM retail_observations WHERE EXISTS(SELECT 1 FROM query_history)",
    "SELECT pg_sleep(1) FROM retail_observations",
    "SELECT set_config('search_path','x',false) FROM retail_observations",
    "SELECT public.count(*) FROM retail_observations",
    "SELECT * FROM retail_observations FOR SHARE",
    "WITH RECURSIVE x AS (SELECT * FROM retail_observations) SELECT * FROM x",
    "SELECT CAST('retail_observations' AS regclass) FROM retail_observations",
    "SELECT * FROM retail_observations LIMIT (SELECT 1)",
    "WITH x AS (DELETE FROM retail_observations RETURNING *) SELECT * FROM x",
])
def test_reject_unsafe_classes(sql):
    with pytest.raises(SQLValidationError):
        validate_sql(sql)


def test_cap_and_cte_shadowing():
    assert "LIMIT 100" in validate_sql("SELECT * FROM retail_observations LIMIT 9999").sql
    assert "LIMIT 5" in validate_sql("SELECT * FROM retail_observations LIMIT 5").sql
    with pytest.raises(SQLValidationError):
        validate_sql(
            "WITH retail_observations AS (SELECT * FROM query_history) "
            "SELECT * FROM retail_observations"
        )
