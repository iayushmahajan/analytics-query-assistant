import json
from datetime import date
from unittest.mock import Mock

import httpx
import pytest
from pydantic import ValidationError

from app.api.schemas.query import QueryPlan, QueryRequest
from app.core.config import settings
from app.scripts import import_market
from app.scripts.import_market import (
    CATEGORIES,
    EU_GEOS,
    add_derived_metrics,
    parse_payload,
    payload_sha256,
)
from app.services.metric_policy import prepare_query
from app.services.sql_generator import generate_query_plan
from app.services.sql_validator import SQLValidationError, validate_sql


def _months(count: int, start: date = date(2015, 1, 1)) -> list[date]:
    output = []
    current = start
    for _ in range(count):
        output.append(current)
        current = date(current.year + (current.month == 12), current.month % 12 + 1, 1)
    return output


def _eurostat_payload(months: int = 24, missing: set[int] | None = None) -> bytes:
    missing = missing or set()
    periods = _months(months)
    dimensions = {
        "freq": {"category": {"index": {"M": 0}}},
        "indic_bt": {"category": {"index": {"VOL_SLS": 0}}},
        "nace_r2": {"category": {
            "index": {code: index for index, code in enumerate(CATEGORIES)},
            "label": {code: f"Label {code}" for code in CATEGORIES},
        }},
        "s_adj": {"category": {"index": {"SCA": 0}}},
        "unit": {"category": {"index": {"I21": 0}}},
        "geo": {"category": {
            "index": {code: index for index, code in enumerate(EU_GEOS)},
            "label": {code: ("Germany" if code == "DE" else f"Country {code}") for code in EU_GEOS},
        }},
        "time": {"category": {
            "index": {period.strftime("%Y-%m"): index for index, period in enumerate(periods)}
        }},
    }
    sizes = [1, 1, len(CATEGORIES), 1, 1, len(EU_GEOS), months]
    cells = len(CATEGORIES) * len(EU_GEOS) * months
    values = {str(index): 90 + (index % months) / 10 for index in range(cells) if index not in missing}
    germany_category_position = CATEGORIES.index("G47") * len(EU_GEOS) * months
    germany_position = germany_category_position + EU_GEOS.index("DE") * months + months - 1
    document = {
        "version": "2.0",
        "class": "dataset",
        "id": ["freq", "indic_bt", "nace_r2", "s_adj", "unit", "geo", "time"],
        "size": sizes,
        "dimension": dimensions,
        "value": values,
        "status": {str(germany_position): "p"},
        "updated": "2026-10-06T11:00:00+0200",
    }
    return json.dumps(document).encode()


def test_only_eurostat_dataset_and_table_are_accepted():
    with pytest.raises(SQLValidationError):
        validate_sql("SELECT SUM(quantity * unit_price) FROM retail_lines")
    plan = QueryPlan(
        status="ready",
        sql="SELECT period, value FROM retail_observations WHERE geo_code = 'DE'",
        metric="retail_index",
        interpretation="German retail index",
        explanation="Read Germany's index",
    )
    assert prepare_query(plan).source_tables == ["retail_observations"]
    with pytest.raises(ValidationError):
        QueryRequest(question="German retail?", dataset="retail")


def test_groq_request_uses_key_and_eurostat_contract(monkeypatch):
    from app.services import sql_generator

    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")
    monkeypatch.setattr(settings, "AI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "AI_MODEL", "openai/gpt-oss-20b")
    post = Mock(return_value=httpx.Response(200, json={"choices": [{"message": {
        "content": '{"status":"blocked","interpretation":"Out of scope","explanation":"Unavailable"}'
    }}]}))
    monkeypatch.setattr(httpx.Client, "post", post)
    plan = generate_query_plan(QueryRequest(question="Customer revenue?"))
    assert plan.status == "blocked"
    assert post.call_args.kwargs["headers"] == {"Authorization": "Bearer test-key"}
    assert post.call_args.kwargs["json"]["response_format"] == {"type": "json_object"}
    prompt = post.call_args.kwargs["json"]["messages"][0]["content"]
    assert "retail_observations" in prompt and "2021=100" in prompt
    monkeypatch.setattr(sql_generator.settings, "AI_API_KEY", "")
    with pytest.raises(sql_generator.ProviderError):
        generate_query_plan(QueryRequest(question="Customer revenue?"))


def test_import_flattens_dimensions_and_calculates_features(monkeypatch):
    monkeypatch.setattr(import_market, "MIN_OBSERVATIONS", 1)
    snapshot = parse_payload(_eurostat_payload())
    assert len(snapshot.observations) == len(CATEGORIES) * len(EU_GEOS) * 24
    assert snapshot.missing_cells == 0
    assert snapshot.source_updated_at.utcoffset() is not None
    assert len(payload_sha256(_eurostat_payload())) == 64
    germany = [
        row for row in snapshot.observations
        if row["geo_code"] == "DE" and row["category_code"] == "G47"
    ]
    assert germany[-1]["status"] == "p"
    assert germany[-1]["monthly_change"] == pytest.approx(0.1)
    assert germany[-1]["yearly_change"] == pytest.approx(1.2)
    assert germany[-1]["rolling_volatility"] is not None


@pytest.mark.parametrize("mutation", [
    "bad_json", "wrong_geo", "wrong_category", "bad_size", "too_short", "non_positive",
])
def test_import_fails_closed_on_unexpected_payloads(monkeypatch, mutation):
    monkeypatch.setattr(import_market, "MIN_OBSERVATIONS", 1)
    if mutation == "bad_json":
        payload = b"not-json"
    else:
        document = json.loads(_eurostat_payload())
        if mutation == "wrong_geo":
            document["dimension"]["geo"]["category"]["index"].pop("DE")
        elif mutation == "wrong_category":
            document["dimension"]["nace_r2"]["category"]["index"].pop("G473")
        elif mutation == "bad_size":
            document["size"][-1] += 1
        elif mutation == "too_short":
            monkeypatch.setattr(import_market, "MIN_OBSERVATIONS", 100_000)
        else:
            document["value"]["0"] = -1
        payload = json.dumps(document).encode()
    with pytest.raises(ValueError):
        parse_payload(payload)


def test_robust_anomaly_detection_uses_only_prior_changes():
    observations = []
    value = 100.0
    for index, period in enumerate(_months(50)):
        if index:
            value += 0.9 if index % 2 else 1.1
        if index == 49:
            value += 8
        observations.append({
            "geo_code": "DE", "geography": "Germany", "category_code": "G47",
            "category": "Total retail", "period": period, "value": value, "status": None,
        })
    add_derived_metrics(observations)
    assert observations[-1]["is_anomaly"] is True
    assert observations[-1]["anomaly_score"] > 3.5
    assert observations[12]["yearly_change"] is not None


def test_missing_month_does_not_create_false_monthly_change():
    observations = [
        {"geo_code": "DE", "geography": "Germany", "category_code": "G47",
         "category": "Total retail", "period": period, "value": 100 + index, "status": None}
        for index, period in enumerate(_months(4)) if index != 2
    ]
    add_derived_metrics(observations)
    assert observations[-1]["monthly_change"] is None
