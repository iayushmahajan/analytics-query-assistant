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
from app.services.result_analysis import analyze_result, build_result_context
from app.services.sql_validator import validate_sql


@pytest.mark.parametrize("content", ["[]", "null", '{"status":"ready"}', '{"status":123}', "not json"])
def test_malformed_model_output(content, monkeypatch):
    response = httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    monkeypatch.setattr(httpx.Client, "post", Mock(return_value=response))
    with pytest.raises(sql_generator.ProviderError) as error:
        sql_generator.generate_query_plan(QueryRequest(question="Revenue"))
    assert error.value.code == "invalid_model_output"


@pytest.mark.parametrize("status,code", [(429, "provider_rate_limited"), (500, "provider_unavailable")])
def test_provider_status_mapping(status, code, monkeypatch):
    monkeypatch.setattr(
        httpx.Client, "post", Mock(return_value=httpx.Response(status, text="secret provider detail"))
    )
    with pytest.raises(sql_generator.ProviderError) as error:
        sql_generator.generate_query_plan(QueryRequest(question="Revenue"))
    assert error.value.code == code
    assert "secret" not in str(error.value)


def test_foundry_local_request_and_fenced_json(monkeypatch):
    content = """```json
{"status":"blocked","interpretation":"Unsafe request","explanation":"Not allowed"}
```"""
    post = Mock(return_value=httpx.Response(200, json={"choices": [{"message": {"content": content}}]}))
    monkeypatch.setattr(httpx.Client, "post", post)

    plan = sql_generator.generate_query_plan(QueryRequest(question="Delete orders"))

    assert plan.status == "blocked"
    assert post.call_args.args == (settings.AI_API_URL,)
    request = post.call_args.kwargs
    assert "headers" not in request
    assert request["json"]["model"] == "phi-4-mini"
    assert "response_format" not in request["json"]
    assert "tools" not in request["json"]


def test_foundry_local_repairs_json_syntax_before_strict_validation(monkeypatch):
    content = """{
"status":"blocked",
"interpretation":"Unsafe request"
"explanation":"Not allowed"
}"""
    response = httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    monkeypatch.setattr(httpx.Client, "post", Mock(return_value=response))

    plan = sql_generator.generate_query_plan(QueryRequest(question="Delete orders"))

    assert plan.status == "blocked"


@pytest.mark.parametrize(
    "content",
    [
        'Here is JSON: {"status":"blocked"}',
        '```json\n{"status":"blocked"}\n``` trailing text',
        '```json\n[{"status":"blocked"}]\n```',
    ],
)
def test_json_extraction_rejects_prose_and_non_objects(content, monkeypatch):
    response = httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    monkeypatch.setattr(httpx.Client, "post", Mock(return_value=response))
    with pytest.raises(sql_generator.ProviderError) as error:
        sql_generator.generate_query_plan(QueryRequest(question="Revenue"))
    assert error.value.code == "invalid_model_output"


def test_plan_types_and_gating():
    with pytest.raises(ValidationError):
        QueryPlan(
            status="needs_clarification",
            sql="SELECT * FROM orders",
            interpretation="x",
            explanation="x",
            clarification_question="Which?",
        )
    with pytest.raises(ValidationError):
        QueryPlan(status="unknown", interpretation="x", explanation="x")


def test_bounded_local_analysis_context():
    sql = validate_sql(
        "SELECT c.full_name AS label, o.total_amount AS amount FROM customers c JOIN orders o ON o.customer_id=c.id"
    )
    result = {
        "columns": ["label", "amount"],
        "rows": [["Private Name", "123.45"]] * 100,
        "row_count": 100,
        "possibly_truncated": True,
    }
    context = build_result_context(result, sql)
    assert "Private Name" in json.dumps(context)
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
    assert "Never add a date filter, dimension, GROUP BY, join, ORDER BY, or LIMIT" in prompt
    assert "orders.customer_id -> customers.id -> customers.country_id -> countries.id" in prompt
    assert 'date_range MUST be "All available dates"' in prompt
    assert "SELECT SUM(o.total_amount) AS total_completed_revenue" in prompt


def test_analysis_context_bounds_even_with_large_column_metadata():
    sql = validate_sql("SELECT name FROM products")
    result = {"columns": ["c" * 5000] * 40, "rows": [["x"] * 40], "row_count": 1, "possibly_truncated": False}
    context = build_result_context(result, sql)
    assert len(json.dumps(context).encode()) <= settings.ANALYSIS_MAX_BYTES


def test_single_value_analysis_is_specific_without_filler():
    plan = QueryPlan(
        status="ready",
        sql="SELECT SUM(total_amount) FROM orders",
        metric="completed_revenue",
        interpretation="Private user input",
        explanation="Private user input",
        date_range="All available dates",
    )
    analysis = analyze_result(
        plan,
        {"columns": ["revenue"], "rows": [["100"]], "row_count": 1, "possibly_truncated": False},
        validate_sql(plan.sql),
    )
    assert analysis.answer == "Completed revenue across all available dates is EUR 100.00."
    assert analysis.findings == analysis.trends == analysis.anomalies == []
    assert analysis.caveats == [
        "This is one aggregate value; explaining changes or differences requires a time or segment breakdown."
    ]
    assert all("currency fluctuation" not in question.lower() for question in analysis.follow_up_questions)


def test_grouped_analysis_calculates_rank_share_trend_and_outlier():
    plan = QueryPlan(
        status="ready",
        sql="SELECT order_date, total_amount FROM orders",
        metric="completed_revenue",
        interpretation="Monthly revenue",
        explanation="Monthly completed revenue",
        date_range="2025",
    )
    result = {
        "columns": ["month", "revenue"],
        "rows": [
            ["2025-01", "100"],
            ["2025-02", "110"],
            ["2025-03", "120"],
            ["2025-04", "500"],
        ],
        "row_count": 4,
        "possibly_truncated": False,
    }
    analysis = analyze_result(plan, result, validate_sql(plan.sql))
    assert "2025-04 has the highest revenue" in analysis.findings[0]
    assert "60.2%" in analysis.findings[0]
    assert "increased by 400.0%" in analysis.trends[0]
    assert "peak occurred in 2025-04" in analysis.trends[1]
    assert "1.5×IQR" in analysis.anomalies[0]


def test_quantity_insights_do_not_format_units_as_currency():
    plan = QueryPlan(
        status="ready",
        sql="SELECT name, quantity FROM products",
        metric="product_sales",
        interpretation="Units by product",
        explanation="Product quantities",
    )
    result = {
        "columns": ["product", "quantity"],
        "rows": [["Keyboard", "6"], ["Book", "5"]],
        "row_count": 2,
        "possibly_truncated": False,
    }
    analysis = analyze_result(plan, result, validate_sql(plan.sql))
    assert "Keyboard has the highest quantity at 6" in analysis.findings[0]
    assert "EUR" not in " ".join(analysis.findings)
