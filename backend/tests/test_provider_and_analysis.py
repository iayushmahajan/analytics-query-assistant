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
from app.services.result_analysis import analyze_result, build_result_context, shape_comparison_result
from app.services.sql_validator import validate_sql


@pytest.mark.parametrize("content", ["[]", "null", '{"status":"ready"}', '{"status":123}', "not json"])
def test_malformed_model_output(content, monkeypatch):
    response = httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    monkeypatch.setattr(httpx.Client, "post", Mock(return_value=response))
    with pytest.raises(sql_generator.ProviderError) as error:
        sql_generator.generate_query_plan(QueryRequest(question="German retail index"))
    assert error.value.code == "invalid_model_output"


@pytest.mark.parametrize("status,code", [(429, "provider_rate_limited"), (500, "provider_unavailable")])
def test_provider_status_mapping(status, code, monkeypatch):
    monkeypatch.setattr(httpx.Client, "post",
                        Mock(return_value=httpx.Response(status, text="secret provider detail")))
    with pytest.raises(sql_generator.ProviderError) as error:
        sql_generator.generate_query_plan(QueryRequest(question="German retail index"))
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
        sql_generator.generate_query_plan(QueryRequest(question="German retail index"))
    assert error.value.code == "invalid_model_output"


def test_plan_types_and_gating():
    with pytest.raises(ValidationError):
        QueryPlan(status="needs_clarification", sql="SELECT * FROM retail_observations",
                  interpretation="x", explanation="x", clarification_question="Which?")
    with pytest.raises(ValidationError):
        QueryPlan(status="unknown", interpretation="x", explanation="x")


def test_bounded_local_analysis_context():
    sql = validate_sql("SELECT geography, value FROM retail_observations")
    result = {"columns": ["geography", "value"], "rows": [["Germany", "99.9"]] * 100,
              "row_count": 100, "possibly_truncated": True}
    context = build_result_context(result, sql)
    assert len(context["rows"]) <= settings.ANALYSIS_MAX_ROWS
    assert len(json.dumps(context).encode()) <= settings.ANALYSIS_MAX_BYTES
    assert context["sampled"]
    result["rows"] = [["x" * 20000, "1"]]
    assert len(json.dumps(build_result_context(result, sql)).encode()) <= settings.ANALYSIS_MAX_BYTES


def test_semantic_contract_used_in_prompt():
    metric = RETAIL_METRICS["retail_index"]
    assert metric.currency is None and metric.date_field == "retail_observations.period"
    prompt = build_sql_generation_messages(QueryRequest(question="German retail index"))[0]["content"]
    assert metric.calculation in prompt
    assert "retail_observations" in prompt
    assert "G47_NFOOD_X_G473" in prompt
    assert "INDEX POINTS" in prompt
    assert "conditional\naggregation" in prompt
    assert "future predictions" in prompt


def test_analysis_context_bounds_large_columns():
    sql = validate_sql("SELECT geography FROM retail_observations")
    result = {"columns": ["c" * 5000] * 40, "rows": [["x"] * 40],
              "row_count": 1, "possibly_truncated": False}
    assert len(json.dumps(build_result_context(result, sql)).encode()) <= settings.ANALYSIS_MAX_BYTES


def test_single_value_analysis_is_specific():
    plan = QueryPlan(status="ready", sql="SELECT MAX(value) FROM retail_observations",
                     metric="retail_index", interpretation="Latest index",
                     explanation="Read the index", date_range="All available dates")
    analysis = analyze_result(plan,
        {"columns": ["retail_index"], "rows": [["100"]], "row_count": 1,
         "possibly_truncated": False}, validate_sql(plan.sql))
    assert analysis.answer == "Retail volume index for all available dates is 100 (2021=100)."
    assert analysis.findings == ["The observation equals the 2021 reference level."]
    assert analysis.trends == analysis.anomalies == analysis.caveats == []


def test_grouped_analysis_uses_non_additive_index_comparisons():
    plan = QueryPlan(status="ready", sql="SELECT period, value FROM retail_observations",
                     metric="retail_index", interpretation="Monthly index",
                     explanation="Monthly index", date_range="2025")
    result = {"columns": ["month", "index_value"], "rows": [
        ["2025-01", "100"], ["2025-02", "110"], ["2025-03", "120"], ["2025-04", "500"]],
        "row_count": 4, "possibly_truncated": False}
    analysis = analyze_result(plan, result, validate_sql(plan.sql))
    assert "2025-04 has the highest index value" in analysis.findings[0]
    assert "returned total" not in analysis.findings[0]
    assert "increased by 400 index points (400.0%)" in analysis.trends[0]
    assert "highest returned level occurred in 2025-04" in analysis.trends[1]
    assert analysis.anomalies == []


def test_index_points_are_not_formatted_as_currency():
    plan = QueryPlan(status="ready", sql="SELECT geography, yearly_change FROM retail_observations",
                     metric="yearly_change", interpretation="Annual change", explanation="Index points")
    result = {"columns": ["geography", "yearly_change"], "rows": [["Germany", "6"], ["France", "5"]],
              "row_count": 2, "possibly_truncated": False}
    analysis = analyze_result(plan, result, validate_sql(plan.sql))
    assert "Germany has the highest yearly change at 6 index points" in analysis.findings[0]
    assert "GBP" not in " ".join(analysis.findings)


def test_single_dated_index_has_direct_answer_and_reference_comparison():
    plan = QueryPlan(status="ready", sql="SELECT period, value FROM retail_observations LIMIT 1",
                     metric="retail_index", interpretation="Latest index", explanation="Latest")
    result = {"columns": ["period", "value"], "rows": [["2026-08-01", "99.9"]],
              "row_count": 1, "possibly_truncated": False}
    analysis = analyze_result(plan, result, validate_sql(plan.sql))
    assert analysis.answer == "Retail volume index for 2026-08-01 is 99.90 (2021=100)."
    assert analysis.findings == ["The observation is 0.10 index points below the 2021 reference level."]


def test_anomaly_observations_use_declared_robust_threshold():
    plan = QueryPlan(status="ready", sql="SELECT period, anomaly_score FROM retail_observations",
                     metric="retail_anomaly_score", interpretation="Anomalies", explanation="Scores")
    result = {"columns": ["period", "anomaly_score"],
              "rows": [["2026-01", "4.2"], ["2026-02", "2.0"]],
              "row_count": 2, "possibly_truncated": False}
    analysis = analyze_result(plan, result, validate_sql(plan.sql))
    assert analysis.anomalies == [
        "2026-01 exceeds the declared anomaly threshold with a robust score of 4.20."
    ]


def test_long_form_time_comparison_is_pivoted_and_analyzed_as_two_series():
    plan = QueryPlan(
        status="ready",
        sql="SELECT period, geography, value FROM retail_observations",
        metric="retail_index",
        interpretation="Compare Germany and EU-27",
        explanation="Aligned comparison",
        date_range="latest 3 months",
        dimensions=["period", "geography"],
    )
    raw = {
        "columns": ["period", "geography", "value"],
        "rows": [
            ["2026-06-01", "Germany", "101.9"], ["2026-06-01", "EU-27", "105.4"],
            ["2026-07-01", "Germany", "98.6"], ["2026-07-01", "EU-27", "104.9"],
            ["2026-08-01", "Germany", "99.9"], ["2026-08-01", "EU-27", "105.0"],
        ],
        "row_count": 6,
        "possibly_truncated": False,
    }
    shaped = shape_comparison_result(plan, raw)
    assert shaped["columns"] == [
        "period", "germany_index", "eu_27_index", "germany_minus_eu_27_gap"
    ]
    assert shaped["row_count"] == 3
    assert shaped["rows"][-1] == ["2026-08-01", "99.9", "105.0", "-5.1"]
    analysis = analyze_result(plan, shaped, validate_sql(plan.sql))
    assert analysis.answer == (
        "From 2026-06-01 to 2026-08-01, Germany decreased from 101.90 to 99.90 "
        "(-2 index points; about -2.0% relative to the starting month), while EU-27 "
        "decreased from 105.40 to 105 (-0.40 index points; about -0.4% relative to the starting month)."
    )
    assert "5.10 index points below EU-27" in analysis.findings[0]
    assert analysis.findings[1] == (
        "Against the 2021=100 baseline, Germany's latest level was 0.10% below the 2021 "
        "average and EU-27's was 5% above it."
    )
    assert analysis.findings[2] == "Germany was above EU-27 in 0 of 3 comparable months."
    assert analysis.trends[0] == "Over the window, Germany underperformed EU-27 by 1.60 index points."
    assert analysis.follow_up_questions[0] == (
        "In which month was the gap between Germany and EU-27 widest?"
    )


def test_comparison_pivot_fails_closed_for_missing_or_truncated_pairs():
    plan = QueryPlan(status="ready", sql="SELECT period, geography, value FROM retail_observations",
                     metric="retail_index", interpretation="Compare", explanation="Compare")
    incomplete = {"columns": ["period", "geography", "value"],
                  "rows": [["2026-08-01", "Germany", "99.9"]],
                  "row_count": 1, "possibly_truncated": False}
    assert shape_comparison_result(plan, incomplete) is incomplete
    truncated = {**incomplete, "rows": [
        ["2026-08-01", "Germany", "99.9"], ["2026-08-01", "EU-27", "105.0"]],
        "row_count": 2, "possibly_truncated": True}
    assert shape_comparison_result(plan, truncated) is truncated
