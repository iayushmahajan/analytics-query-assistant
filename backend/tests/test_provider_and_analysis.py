import json
from unittest.mock import Mock

import httpx
import pytest
from pydantic import ValidationError

from app.api.schemas.query import QueryPlan, QueryRequest
from app.constants.metrics import METRICS
from app.core.config import settings
from app.services import sql_generator
from app.services.prompt_builder import build_sql_generation_messages
from app.services.result_analysis import build_result_context
from app.services.sql_validator import validate_sql


@pytest.mark.parametrize("content", ['[]', 'null', '{"status":"ready"}', '{"status":123}', 'not json'])
def test_malformed_model_output(content, monkeypatch):
    response = httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    monkeypatch.setattr(httpx.Client, "post", Mock(return_value=response))
    with pytest.raises(sql_generator.ProviderError) as error:
        sql_generator.generate_query_plan(QueryRequest(question="Revenue"))
    assert error.value.code == "invalid_model_output"


@pytest.mark.parametrize("status,code", [(429,"provider_rate_limited"),(500,"provider_unavailable")])
def test_provider_status_mapping(status, code, monkeypatch):
    monkeypatch.setattr(httpx.Client, "post", Mock(return_value=httpx.Response(status, text="secret provider detail")))
    with pytest.raises(sql_generator.ProviderError) as error:
        sql_generator.generate_query_plan(QueryRequest(question="Revenue"))
    assert error.value.code == code
    assert "secret" not in str(error.value)


def test_plan_types_and_gating():
    with pytest.raises(ValidationError):
        QueryPlan(status="needs_clarification", sql="SELECT * FROM orders", interpretation="x", explanation="x", clarification_question="Which?")
    with pytest.raises(ValidationError):
        QueryPlan(status="unknown", interpretation="x", explanation="x")


def test_bounded_and_alias_safe_context():
    sql = validate_sql("SELECT c.full_name AS label, o.total_amount AS amount FROM customers c JOIN orders o ON o.customer_id=c.id")
    result = {"columns": ["label", "amount"], "rows": [["Private Name", "123.45"]] * 100, "row_count":100,"possibly_truncated":True}
    context = build_result_context(result, sql)
    assert "Private" not in json.dumps(context)
    assert len(context["rows"]) <= settings.ANALYSIS_MAX_ROWS
    assert len(json.dumps(context).encode()) <= settings.ANALYSIS_MAX_BYTES
    assert context["sampled"]
    sql = validate_sql("SELECT name FROM products")
    result["rows"] = [["x" * 20000, "1"]]
    assert len(json.dumps(build_result_context(result, sql)).encode()) <= settings.ANALYSIS_MAX_BYTES


def test_semantic_contract_used_in_prompt():
    revenue = METRICS["revenue"]
    assert revenue.included_statuses == ["completed"]
    assert revenue.excluded_statuses == ["pending", "cancelled"]
    assert revenue.currency == "EUR" and revenue.date_field == "orders.order_date"
    assert METRICS["customer_count"].date_field == "customers.created_at"
    assert "unit_price" in METRICS["category_sales"].calculation
    prompt = build_sql_generation_messages(QueryRequest(question="Revenue"))[0]["content"]
    assert revenue.calculation in prompt
