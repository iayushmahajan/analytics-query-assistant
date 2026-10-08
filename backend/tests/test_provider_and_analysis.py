import json
from unittest.mock import Mock

import httpx
import pytest
from pydantic import ValidationError

from app.api.schemas.query import QueryPlan, QueryRequest
from app.constants.metrics import RETAIL_METRICS
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
        sql_generator.generate_query_plan(QueryRequest(question="Gross sales"))
    assert error.value.code == "invalid_model_output"


@pytest.mark.parametrize("status,code", [(429, "provider_rate_limited"), (500, "provider_unavailable")])
def test_provider_status_mapping(status, code, monkeypatch):
    monkeypatch.setattr(httpx.Client, "post",
                        Mock(return_value=httpx.Response(status, text="secret provider detail")))
    with pytest.raises(sql_generator.ProviderError) as error:
        sql_generator.generate_query_plan(QueryRequest(question="Gross sales"))
    assert error.value.code == code
    assert "secret" not in str(error.value)


def test_foundry_local_request_and_fenced_json(monkeypatch):
    content = '```json\n{"status":"blocked","interpretation":"Unsafe request","explanation":"Not allowed"}\n```'
    post = Mock(return_value=httpx.Response(200, json={"choices": [{"message": {"content": content}}]}))
    monkeypatch.setattr(httpx.Client, "post", post)
    plan = sql_generator.generate_query_plan(QueryRequest(question="Delete rows"))
    assert plan.status == "blocked"
    assert post.call_args.args == (settings.AI_API_URL,)
    assert "headers" not in post.call_args.kwargs
    assert post.call_args.kwargs["json"]["model"] == "phi-4-mini"
    assert "response_format" not in post.call_args.kwargs["json"]


def test_foundry_local_repairs_json_syntax_before_strict_validation(monkeypatch):
    content = '{"status":"blocked","interpretation":"Unsafe request" "explanation":"Not allowed"}'
    response = httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    monkeypatch.setattr(httpx.Client, "post", Mock(return_value=response))
    assert sql_generator.generate_query_plan(QueryRequest(question="Delete rows")).status == "blocked"


@pytest.mark.parametrize("content", [
    'Here is JSON: {"status":"blocked"}',
    '```json\n{"status":"blocked"}\n``` trailing text',
    '```json\n[{"status":"blocked"}]\n```',
])
def test_json_extraction_rejects_prose_and_non_objects(content, monkeypatch):
    response = httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    monkeypatch.setattr(httpx.Client, "post", Mock(return_value=response))
    with pytest.raises(sql_generator.ProviderError) as error:
        sql_generator.generate_query_plan(QueryRequest(question="Gross sales"))
    assert error.value.code == "invalid_model_output"


def test_plan_types_and_gating():
    with pytest.raises(ValidationError):
        QueryPlan(status="needs_clarification", sql="SELECT * FROM retail_lines",
                  interpretation="x", explanation="x", clarification_question="Which?")
    with pytest.raises(ValidationError):
        QueryPlan(status="unknown", interpretation="x", explanation="x")


def test_bounded_local_analysis_context():
    sql = validate_sql("SELECT country, quantity FROM retail_lines")
    result = {"columns": ["country", "quantity"], "rows": [["United Kingdom", "123"]] * 100,
              "row_count": 100, "possibly_truncated": True}
    context = build_result_context(result, sql)
    assert len(context["rows"]) <= settings.ANALYSIS_MAX_ROWS
    assert len(json.dumps(context).encode()) <= settings.ANALYSIS_MAX_BYTES
    assert context["sampled"]
    result["rows"] = [["x" * 20000, "1"]]
    assert len(json.dumps(build_result_context(result, sql)).encode()) <= settings.ANALYSIS_MAX_BYTES


def test_semantic_contract_used_in_prompt():
    metric = RETAIL_METRICS["retail_gross_sales"]
    assert metric.included_statuses == ["sale"]
    assert metric.currency == "GBP" and metric.date_field == "retail_lines.invoice_date"
    prompt = build_sql_generation_messages(QueryRequest(question="Gross sales"))[0]["content"]
    assert metric.calculation in prompt
    assert "retail_lines" in prompt
    assert "No product categories" in prompt
    assert "net revenue after returns" in prompt


def test_analysis_context_bounds_large_columns():
    sql = validate_sql("SELECT country FROM retail_lines")
    result = {"columns": ["c" * 5000] * 40, "rows": [["x"] * 40],
              "row_count": 1, "possibly_truncated": False}
    assert len(json.dumps(build_result_context(result, sql)).encode()) <= settings.ANALYSIS_MAX_BYTES


def test_single_value_analysis_is_specific():
    plan = QueryPlan(status="ready", sql="SELECT SUM(quantity * unit_price) FROM retail_lines",
                     metric="retail_gross_sales", interpretation="Gross sales",
                     explanation="Sale value", date_range="All available dates")
    analysis = analyze_result(plan,
        {"columns": ["gross_sales"], "rows": [["100"]], "row_count": 1,
         "possibly_truncated": False}, validate_sql(plan.sql))
    assert analysis.answer == "Gross sales across all available dates is GBP 100.00."
    assert analysis.findings == analysis.trends == analysis.anomalies == []
    assert len(analysis.caveats) == 1


def test_grouped_analysis_rank_share_trend_and_outlier():
    plan = QueryPlan(status="ready", sql="SELECT invoice_date, quantity FROM retail_lines",
                     metric="retail_units", interpretation="Monthly units",
                     explanation="Monthly units", date_range="2011")
    result = {"columns": ["month", "units"], "rows": [
        ["2011-01", "100"], ["2011-02", "110"], ["2011-03", "120"], ["2011-04", "500"]],
        "row_count": 4, "possibly_truncated": False}
    analysis = analyze_result(plan, result, validate_sql(plan.sql))
    assert "2011-04 has the highest units" in analysis.findings[0]
    assert "60.2%" in analysis.findings[0]
    assert "increased by 400.0%" in analysis.trends[0]
    assert "peak occurred in 2011-04" in analysis.trends[1]
    assert "1.5×IQR" in analysis.anomalies[0]


def test_quantity_not_formatted_as_currency():
    plan = QueryPlan(status="ready", sql="SELECT description, quantity FROM retail_lines",
                     metric="retail_units", interpretation="Units by product", explanation="Units")
    result = {"columns": ["product", "quantity"], "rows": [["Paper", "6"], ["Book", "5"]],
              "row_count": 2, "possibly_truncated": False}
    analysis = analyze_result(plan, result, validate_sql(plan.sql))
    assert "Paper has the highest quantity at 6" in analysis.findings[0]
    assert "GBP" not in " ".join(analysis.findings)
