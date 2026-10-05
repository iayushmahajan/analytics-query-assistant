import pytest
from sqlglot import parse_one

from app.services.sql_validator import SQLValidationError, validate_sql


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM orders",
        "SELECT SUM(total_amount) FROM orders",
        "SELECT * FROM orders WHERE status='completed' AND (total_amount > 1 OR customer_id=2)",
        "SELECT * FROM orders WHERE EXISTS(SELECT 1 FROM products)",
        "SELECT p.name FROM products p JOIN categories c ON c.id=p.category_id",
        "WITH x AS (SELECT * FROM orders) SELECT * FROM x",
        'SELECT * FROM "orders"',
        "SELECT * FROM public.orders -- safe comment",
        "SELECT * FROM products WHERE name = 'Drop earrings'",
        "SELECT * FROM orders WHERE customer_id IN (SELECT id FROM customers LIMIT 1)",
        "SELECT 'limit 1' FROM orders",
        "SELECT id FROM orders UNION SELECT id FROM orders",
    ],
)
def test_safe_analytics_have_outer_limit(sql):
    validated = validate_sql(sql)
    assert int(parse_one(validated.sql, read="postgres").args["limit"].expression.this) <= 100


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM orders",
        "SELECT * INTO stolen FROM orders",
        "SELECT * FROM orders; SELECT * FROM products",
        "BEGIN",
        "SELECT * FROM query_history",
        "SELECT * FROM orders, query_history",
        'SELECT * FROM orders o JOIN "query_history" h ON true',
        "WITH x AS (SELECT * FROM query_history) SELECT * FROM x",
        "SELECT * FROM private.orders",
        "SELECT * FROM pg_catalog.pg_class",
        "SELECT * FROM orders UNION SELECT * FROM query_history",
        "SELECT * FROM orders WHERE EXISTS(SELECT 1 FROM query_history)",
        "SELECT pg_sleep(1) FROM orders",
        "SELECT set_config('search_path','x',false) FROM orders",
        "SELECT public.count(*) FROM orders",
        "SELECT * FROM orders FOR SHARE",
        "WITH RECURSIVE x AS (SELECT * FROM orders) SELECT * FROM x",
        "SELECT CAST('orders' AS regclass) FROM orders",
        "SELECT * FROM orders LIMIT (SELECT 1)",
        "WITH orders AS (DELETE FROM products RETURNING *) SELECT * FROM orders",
    ],
)
def test_reject_unsafe_classes(sql):
    with pytest.raises(SQLValidationError):
        validate_sql(sql)


def test_cap_and_cte_shadowing():
    assert "LIMIT 100" in validate_sql("SELECT * FROM orders LIMIT 9999").sql
    assert "LIMIT 5" in validate_sql("SELECT * FROM orders LIMIT 5").sql
    with pytest.raises(SQLValidationError):
        validate_sql("WITH orders AS (SELECT * FROM query_history) SELECT * FROM orders")
