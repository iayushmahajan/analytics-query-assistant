from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.api.schemas.query import QueryPlan, ResultAnalysis
from app.models import QueryHistory
from app.services import query_workflow as workflow
from app.services.sql_executor import SQLExecutionError
from app.services.sql_generator import ProviderError


@pytest.fixture
def stages(monkeypatch):
    plan = QueryPlan(
        status="ready",
        sql="SELECT SUM(total_amount) AS revenue FROM orders WHERE status='completed'",
        metric="revenue",
        interpretation="Completed revenue",
        explanation="Sum completed order totals",
    )
    generate = Mock(return_value=plan)
    execute = Mock(
        return_value={
            "columns": ["revenue"],
            "rows": [["123.45"]],
            "row_count": 1,
            "execution_time_ms": 2,
            "possibly_truncated": False,
        }
    )
    analyze = Mock(return_value=ResultAnalysis(answer="Completed revenue is EUR 123.45."))
    for name, mock in [
        ("generate_query_plan", generate),
        ("execute_select_sql", execute),
        ("analyze_result", analyze),
    ]:
        monkeypatch.setattr(workflow, name, mock)
    return generate, execute, analyze


def test_success_snapshot_restore_and_continuation(client, stages):
    result = client.post("/query", json={"question": "Revenue?"})
    assert result.status_code == 200
    data = result.json()
    assert data["status"] == "success"
    assert data["plan"]["source_tables"] == ["orders"]
    assert client.get(f"/history/{data['id']}").json() == data
    assert client.get("/history").json()[0]["question"] == "Revenue?"
    assert result.headers["x-request-id"] == data["request_id"]


def test_clarification_never_executes_and_can_continue(client, stages):
    generate, execute, analyze = stages
    generate.return_value = QueryPlan(
        status="needs_clarification",
        interpretation="Performance is undefined",
        explanation="Choose a metric",
        clarification_question="Revenue or order count?",
    )
    data = client.post("/query", json={"question": "Performance?"}).json()
    assert data["status"] == "needs_clarification"
    execute.assert_not_called()
    analyze.assert_not_called()
    generate.return_value = QueryPlan(
        status="ready",
        sql="SELECT COUNT(*) AS orders FROM orders",
        metric="order_count",
        interpretation="All orders",
        explanation="Count orders",
    )
    result = client.post(
        "/query",
        json={
            "question": "Performance?",
            "clarification": [{"question": "Revenue or order count?", "answer": "Order count"}],
        },
    )
    assert result.json()["status"] == "success"
    assert generate.call_args.args[0].clarification[0].answer == "Order count"


def test_blocked_sql_never_executes(client, stages):
    stages[0].return_value.sql = "SELECT * FROM query_history"
    data = client.post("/query", json={"question": "History?"}).json()
    assert data["status"] == "blocked"
    stages[1].assert_not_called()


@pytest.mark.parametrize("code,http", [("execution_failed", 422), ("query_timeout", 504)])
def test_execution_failure_saved(client, db, stages, code, http):
    stages[1].side_effect = SQLExecutionError(code)
    result = client.post("/query", json={"question": "Revenue?"})
    assert result.status_code == http
    assert result.json()["error"]["code"] == code
    assert db.query(QueryHistory).count() == 1
    stages[2].assert_not_called()


@pytest.mark.parametrize(
    "code,http",
    [
        ("provider_unavailable", 503),
        ("provider_rate_limited", 429),
        ("invalid_model_output", 502),
        ("provider_timeout", 504),
    ],
)
def test_provider_failure_saved(client, db, stages, code, http):
    stages[0].side_effect = ProviderError(code, "Public error", http)
    result = client.post("/query", json={"question": "Revenue?"})
    assert result.status_code == http
    assert result.json()["error"]["code"] == code
    assert db.query(QueryHistory).count() == 1
    stages[1].assert_not_called()


def test_analysis_failure_preserves_results(client, stages):
    stages[2].side_effect = ValueError("Could not calculate insights")
    data = client.post("/query", json={"question": "Revenue?"}).json()
    assert data["status"] == "success" and data["rows"] == [["123.45"]]
    assert data["analysis"] is None and data["warnings"]


def test_history_failure_rolls_back(client, db, stages, monkeypatch):
    rollback = Mock(wraps=db.rollback)
    monkeypatch.setattr(db, "commit", Mock(side_effect=SQLAlchemyError("private internal details")))
    monkeypatch.setattr(db, "rollback", rollback)
    data = client.post("/query", json={"question": "Revenue?"}).json()
    assert data["status"] == "success" and data["id"] is None
    assert "private" not in str(data)
    rollback.assert_called_once()


def test_invalid_request_and_missing_history(client):
    assert client.post("/query", json={"question": "   "}).status_code == 422
    assert client.get("/history/999").status_code == 404
