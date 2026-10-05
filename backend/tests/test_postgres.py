import os
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.schemas.query import QueryPlan, QueryRequest, ResultAnalysis
from app.core.config import settings
from app.models import Base, QueryHistory
from app.scripts.seed import seed_demo
from app.services import query_workflow, sql_executor
from app.services.sql_executor import SQLExecutionError, execute_select_sql
from app.services.sql_validator import ValidatedSQL, validate_sql
from evals.evaluate import CASES, evaluate_plan

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def postgres():
    url = os.getenv("TEST_DATABASE_URL")
    reader_url = os.getenv("TEST_ANALYTICS_DATABASE_URL")
    if not url or not reader_url or os.getenv("TEST_ALLOW_RESET") != "1":
        pytest.skip(
            "Requires explicitly disposable TEST_DATABASE_URL, TEST_ANALYTICS_DATABASE_URL, TEST_ALLOW_RESET=1"
        )
    env = dict(os.environ, DATABASE_URL=url)
    subprocess.run(["alembic", "upgrade", "head"], check=True, env=env)
    subprocess.run(["python", "-m", "app.scripts.apply_grants"], check=True, env=env)
    app_engine = create_engine(url)
    reader = create_engine(reader_url)
    with app_engine.begin() as connection:
        connection.execute(text((Path(__file__).parents[1] / "evals/fixture.sql").read_text()))
    yield app_engine, reader
    app_engine.dispose()
    reader.dispose()


def test_migration_metadata_and_seed(postgres):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    engine, _ = postgres
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    signatures = []
    for _ in range(2):
        with Session(engine) as session:
            seed_demo(session, reset=True)
            signatures.append(session.execute(text("SELECT COUNT(*), SUM(total_amount) FROM orders")).one())
            assert (
                session.execute(
                    text(
                        "SELECT COUNT(*) FROM orders o JOIN customers c ON c.id=o.customer_id WHERE o.order_date<c.created_at::date"
                    )
                ).scalar()
                == 0
            )
    assert signatures[0] == signatures[1] and signatures[0][0] > 1000
    with engine.begin() as connection:
        connection.execute(text((Path(__file__).parents[1] / "evals/fixture.sql").read_text()))


def test_database_boundary_even_without_validator(postgres):
    _, reader = postgres
    for sql in [
        "SELECT * FROM query_history",
        "SELECT email FROM customers",
        "INSERT INTO categories(name) VALUES ('bad')",
        "UPDATE orders SET total_amount=0",
        "SELECT * INTO stolen FROM orders",
        "CREATE TEMP TABLE stolen(id int)",
    ]:
        with reader.connect() as connection:
            with pytest.raises(DBAPIError):
                connection.execute(text(sql))
            connection.rollback()
            assert connection.execute(text("SELECT COUNT(*) FROM orders")).scalar() > 0
    # Even if read-only mode is disabled, object privileges still forbid mutation.
    with reader.connect() as connection:
        connection.execute(text("SET TRANSACTION READ WRITE"))
        with pytest.raises(DBAPIError):
            connection.execute(text("UPDATE orders SET total_amount=0"))
        connection.rollback()


def test_constraints(postgres):
    engine, _ = postgres
    for sql in [
        "UPDATE orders SET status='invalid' WHERE id=1",
        "UPDATE orders SET total_amount=-1 WHERE id=1",
        "UPDATE order_items SET quantity=0 WHERE id=1",
        "UPDATE products SET price=-1 WHERE id=1",
    ]:
        with engine.connect() as connection:
            with pytest.raises(DBAPIError):
                connection.execute(text(sql))
            connection.rollback()


def test_execution_timeout_rollback_and_limit(postgres, monkeypatch):
    engine, reader = postgres
    monkeypatch.setattr(sql_executor, "analytics_engine", reader)
    monkeypatch.setattr(settings, "SQL_STATEMENT_TIMEOUT_MS", 100)
    with pytest.raises(SQLExecutionError) as error:
        execute_select_sql(ValidatedSQL("SELECT pg_sleep(1) FROM orders LIMIT 1", ["orders"], False))
    assert error.value.code == "query_timeout"
    # Same pool remains usable; application writes are a separate transaction.
    assert execute_select_sql(validate_sql("SELECT COUNT(*) AS orders FROM orders"))["rows"] == [[6]]
    monkeypatch.setattr(settings, "MAX_SQL_ROWS", 2)
    result = execute_select_sql(
        validate_sql("SELECT id FROM orders WHERE id IN (SELECT id FROM orders LIMIT 5)")
    )
    assert result["row_count"] == 2
    with Session(engine) as session:
        session.add(
            QueryHistory(question="timeout", generated_sql="", explanation="timeout", status="failed")
        )
        session.commit()


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["question"])
def test_golden_reference_results(postgres, monkeypatch, case):
    _, reader = postgres
    monkeypatch.setattr(sql_executor, "analytics_engine", reader)
    plan = QueryPlan(
        status=case["status"],
        sql=case.get("sql"),
        metric=case["metric"],
        interpretation=case["question"],
        explanation="Golden reference",
        filters=case["filters"],
        clarification_question=case.get("clarification_question"),
    )
    evaluate_plan(case, plan)


def test_workflow_real_history_and_results(postgres, monkeypatch):
    engine, reader = postgres
    monkeypatch.setattr(sql_executor, "analytics_engine", reader)
    monkeypatch.setattr(
        query_workflow,
        "generate_query_plan",
        Mock(
            return_value=QueryPlan(
                status="ready",
                sql="SELECT SUM(total_amount) AS revenue FROM orders WHERE status='completed'",
                metric="revenue",
                interpretation="Revenue",
                explanation="Completed totals",
            )
        ),
    )
    monkeypatch.setattr(
        query_workflow, "analyze_result", Mock(return_value=ResultAnalysis(answer="Revenue is EUR 400."))
    )
    with Session(engine) as db:
        result, status = query_workflow.run_analysis(QueryRequest(question="Revenue?"), db, "postgres-test")
        assert status == 200 and result.rows == [["400.00"]]
        assert db.get(QueryHistory, result.id).snapshot["analysis"]["answer"] == "Revenue is EUR 400."


def test_owner_credentials_fail_closed(postgres, monkeypatch):
    engine, _ = postgres
    monkeypatch.setattr(sql_executor, "analytics_engine", engine)
    with pytest.raises(SQLExecutionError):
        execute_select_sql(validate_sql("SELECT COUNT(*) FROM orders"))


def test_execution_failure_history_uses_independent_transaction(postgres, monkeypatch):
    engine, reader = postgres
    monkeypatch.setattr(sql_executor, "analytics_engine", reader)
    monkeypatch.setattr(
        query_workflow,
        "generate_query_plan",
        Mock(
            return_value=QueryPlan(
                status="ready",
                sql="SELECT missing_column FROM orders",
                metric="revenue",
                interpretation="Revenue",
                explanation="Invalid model column",
            )
        ),
    )
    with Session(engine) as db:
        result, status = query_workflow.run_analysis(QueryRequest(question="Revenue?"), db, "failure-test")
        assert status == 422 and result.error.code == "execution_failed"
        assert db.get(QueryHistory, result.id).snapshot["status"] == "failed"
    assert execute_select_sql(validate_sql("SELECT COUNT(*) FROM orders"))["rows"] == [[6]]


def test_canonical_revenue_applied_even_when_model_omits_status(postgres, monkeypatch):
    from app.services.metric_policy import prepare_query

    _, reader = postgres
    monkeypatch.setattr(sql_executor, "analytics_engine", reader)
    for sql in [
        "SELECT SUM(total_amount) FROM orders",
        "WITH x AS (SELECT * FROM orders WHERE status='pending' OR 1=1) SELECT SUM(total_amount) FROM x",
    ]:
        plan = QueryPlan(
            status="ready", sql=sql, metric="revenue", interpretation="Revenue", explanation="Revenue"
        )
        assert execute_select_sql(prepare_query(plan))["rows"] == [["400.00"]]
