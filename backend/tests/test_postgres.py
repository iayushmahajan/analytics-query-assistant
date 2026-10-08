"""Integration checks require an explicitly disposable PostgreSQL database."""

import os
import subprocess
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.schemas.query import QueryPlan, QueryRequest
from app.models import Base
from app.services import query_workflow, sql_executor
from app.services.metric_policy import prepare_query
from app.services.sql_executor import SQLExecutionError, execute_select_sql
from app.services.sql_validator import validate_sql

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def postgres():
    url = os.getenv("TEST_DATABASE_URL")
    reader_url = os.getenv("TEST_ANALYTICS_DATABASE_URL")
    if not url or not reader_url or os.getenv("TEST_ALLOW_RESET") != "1":
        pytest.skip("Requires disposable TEST_DATABASE_URL, TEST_ANALYTICS_DATABASE_URL, TEST_ALLOW_RESET=1")
    env = dict(os.environ, DATABASE_URL=url)
    subprocess.run(["alembic", "upgrade", "head"], check=True, env=env)
    subprocess.run(["python", "-m", "app.scripts.apply_grants"], check=True, env=env)
    owner = create_engine(url)
    reader = create_engine(reader_url)
    with owner.begin() as connection:
        connection.execute(text(
            "TRUNCATE retail_lines, retail_imports, market_observations, market_forecasts, "
            "market_imports, query_history RESTART IDENTITY"
        ))
        connection.execute(text("""
            INSERT INTO retail_lines(invoice_no, stock_code, description, quantity,
                unit_price, invoice_date, country, is_sale) VALUES
            ('1001','A1','Paper',2,10,'2011-01-01','United Kingdom',true),
            ('1002','A1','Paper',3,20,'2011-01-02','France',true),
            ('C1003','A1','Paper',-1,10,'2011-01-03','France',false)
        """))
        connection.execute(text("""
            INSERT INTO market_observations(period, value, status)
            VALUES ('2026-08-01', 99.9, 'p')
        """))
    yield owner, reader
    owner.dispose()
    reader.dispose()


def test_schema_is_retail_only(postgres):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    owner, _ = postgres
    with owner.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        assert connection.execute(text("SELECT to_regclass('public.orders')")).scalar() is None


def test_reader_boundary_and_sale_population(postgres, monkeypatch):
    _, reader = postgres
    monkeypatch.setattr(sql_executor, "analytics_engine", reader)
    for sql in [
        "SELECT * FROM query_history",
        "UPDATE retail_lines SET quantity=0",
        "UPDATE market_observations SET value=0",
        "CREATE TEMP TABLE stolen(id int)",
    ]:
        with reader.connect() as connection:
            with pytest.raises(DBAPIError):
                connection.execute(text(sql))
            connection.rollback()
    with reader.connect() as connection:
        assert float(connection.execute(text("SELECT value FROM market_observations")).scalar()) == 99.9
    plan = QueryPlan(status="ready", sql="SELECT SUM(quantity * unit_price) AS gross_sales FROM retail_lines",
                     metric="retail_gross_sales", interpretation="Gross sales", explanation="Sale value")
    assert execute_select_sql(prepare_query(plan))["rows"] == [["80.00"]]


def test_workflow_and_history(postgres, monkeypatch):
    owner, reader = postgres
    monkeypatch.setattr(sql_executor, "analytics_engine", reader)
    monkeypatch.setattr(query_workflow, "generate_query_plan", Mock(return_value=QueryPlan(
        status="ready", sql="SELECT SUM(quantity * unit_price) AS gross_sales FROM retail_lines",
        metric="retail_gross_sales", interpretation="Gross sales", explanation="Sale value")))
    with Session(owner) as db:
        result, status = query_workflow.run_analysis(QueryRequest(question="Gross sales?"), db, "postgres-test")
        assert status == 200 and result.rows == [["80.00"]]
        assert result.analysis.answer == "Gross sales across all available dates is GBP 80.00."


def test_owner_credentials_fail_closed(postgres, monkeypatch):
    owner, _ = postgres
    monkeypatch.setattr(sql_executor, "analytics_engine", owner)
    with pytest.raises(SQLExecutionError):
        execute_select_sql(validate_sql("SELECT COUNT(*) FROM retail_lines"))
