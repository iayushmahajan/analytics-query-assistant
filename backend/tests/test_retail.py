import csv
import json
import zipfile
from datetime import date, datetime
from unittest.mock import Mock

import httpx
import pytest
from openpyxl import Workbook
from pydantic import ValidationError

from app.api.schemas.query import QueryPlan, QueryRequest
from app.core.config import settings
from app.scripts.import_market import parse_payload, payload_sha256
from app.scripts.import_retail import archive_sha256, convert_archive
from app.scripts.train_market import build_forecast, month_after
from app.services.metric_policy import prepare_query
from app.services.sql_generator import generate_query_plan
from app.services.sql_validator import SQLValidationError, validate_sql


def test_retail_queries_cannot_reach_removed_tables_or_non_sale_population():
    with pytest.raises(SQLValidationError):
        validate_sql("SELECT SUM(total_amount) FROM orders")
    plan = QueryPlan(status="ready", sql="SELECT SUM(quantity * unit_price) FROM retail_lines",
                     metric="retail_gross_sales", interpretation="Gross sales", explanation="Sum sale lines")
    checked = prepare_query(plan)
    assert "is_sale = TRUE" in checked.sql
    with pytest.raises(ValidationError):
        QueryRequest(question="Gross sales?", dataset="demo")


def test_groq_request_uses_key_and_validated_contract(monkeypatch):
    from app.services import sql_generator

    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")
    monkeypatch.setattr(settings, "AI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "AI_MODEL", "openai/gpt-oss-20b")
    post = Mock(return_value=httpx.Response(200, json={"choices": [{"message": {
        "content": '{"status":"blocked","interpretation":"Out of scope","explanation":"Unavailable"}'
    }}]}))
    monkeypatch.setattr(httpx.Client, "post", post)
    plan = generate_query_plan(QueryRequest(question="Profit?", dataset="retail"))
    assert plan.status == "blocked"
    assert post.call_args.kwargs["headers"] == {"Authorization": "Bearer test-key"}
    assert post.call_args.kwargs["json"]["response_format"] == {"type": "json_object"}
    assert "retail_lines" in post.call_args.kwargs["json"]["messages"][0]["content"]
    monkeypatch.setattr(sql_generator.settings, "AI_API_KEY", "")
    with pytest.raises(sql_generator.ProviderError):
        generate_query_plan(QueryRequest(question="Profit?", dataset="retail"))


def test_import_tracks_cancellations_without_customer_identifiers(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"])
    sheet.append(["100001", "A1", "Product", 3, datetime(2011, 1, 1), 2.5, 12345, "United Kingdom"])
    sheet.append(["C100002", "A1", "Product", -1, datetime(2011, 1, 2), 2.5, 12345, "United Kingdom"])
    xlsx = tmp_path / "retail.xlsx"
    workbook.save(xlsx)
    archive = tmp_path / "retail.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.write(xlsx, "retail.xlsx")
    output = tmp_path / "rows.csv"
    assert convert_archive(archive, output, min_rows=2) == (2, 0)
    with output.open() as source:
        rows = list(csv.reader(source))
    assert len(rows[0]) == 8
    assert rows[0][-1] == "True" and rows[1][-1] == "False"
    assert "12345" not in output.read_text()
    assert len(archive_sha256(archive)) == 64


def _months(count: int, start: date = date(2010, 1, 1)) -> list[date]:
    output = []
    current = start
    for _ in range(count):
        output.append(current)
        current = month_after(current)
    return output


def _eurostat_payload(count: int = 132, missing: set[int] | None = None) -> bytes:
    missing = missing or set()
    periods = _months(count)
    dimensions = {
        name: {"category": {"index": {code: 0}}}
        for name, code in {
            "freq": "M", "indic_bt": "VOL_SLS", "nace_r2": "G47",
            "s_adj": "SCA", "unit": "I21", "geo": "DE",
        }.items()
    }
    dimensions["time"] = {
        "category": {"index": {period.strftime("%Y-%m"): i for i, period in enumerate(periods)}}
    }
    document = {
        "version": "2.0", "class": "dataset",
        "id": ["freq", "indic_bt", "nace_r2", "s_adj", "unit", "geo", "time"],
        "size": [1, 1, 1, 1, 1, 1, count], "dimension": dimensions,
        "value": {str(i): 90 + i / 10 for i in range(count) if i not in missing},
        "status": {str(count - 1): "p"}, "updated": "2026-10-06T11:00:00+0200",
    }
    return json.dumps(document).encode()


def test_market_import_validates_dimensions_missing_values_and_provisional_status():
    payload = _eurostat_payload(missing={0, 1})
    snapshot = parse_payload(payload)
    assert len(snapshot.observations) == 130
    assert snapshot.missing_periods == 2
    assert snapshot.observations[-1]["status"] == "p"
    assert snapshot.source_updated_at.utcoffset() is not None
    assert len(payload_sha256(payload)) == 64


@pytest.mark.parametrize("mutation", ["bad_json", "wrong_geo", "too_short", "non_positive"])
def test_market_import_fails_closed_on_unexpected_payloads(mutation):
    if mutation == "bad_json":
        payload = b"not-json"
    else:
        document = json.loads(_eurostat_payload(132))
        if mutation == "wrong_geo":
            document["dimension"]["geo"]["category"]["index"] = {"FR": 0}
        elif mutation == "too_short":
            document = json.loads(_eurostat_payload(119))
        else:
            document["value"]["131"] = -1
        payload = json.dumps(document).encode()
    with pytest.raises(ValueError):
        parse_payload(payload)


def test_market_forecast_uses_separate_validation_and_test_windows():
    periods = _months(180)
    observations = [
        (period, 100 + i * 0.03 + 2 * (i % 12 == 11), "p" if i == 179 else None)
        for i, period in enumerate(periods)
    ]
    forecast = build_forecast(observations)
    assert forecast["target_period"] == month_after(periods[-1])
    assert len(forecast["backtest"]) == 24
    assert forecast["validation_months"] == 24 and forecast["test_months"] == 24
    assert forecast["test_mae"] >= 0 and forecast["baseline_test_mae"] >= 0
    assert 0 <= forecast["interval_coverage"] <= 1
    assert forecast["prediction_lower"] <= forecast["predicted_index"] <= forecast["prediction_upper"]
    assert forecast["confidence"] in {"supported", "limited", "insufficient"}
    assert forecast["latest_observation_status"] == "p"


def test_market_forecast_prefers_a_simple_baseline_when_ml_has_no_material_gain():
    observations = [(period, 100.0, None) for period in _months(150)]
    forecast = build_forecast(observations)
    assert forecast["method"] == "last_value"
    assert forecast["test_mae"] == 0
    assert forecast["test_wape"] == 0


def test_market_forecast_rejects_short_contiguous_suffix_and_invalid_values():
    old = [(period, 100.0, None) for period in _months(130, date(2000, 1, 1))]
    recent = [(period, 101.0, None) for period in _months(119, date(2020, 1, 1))]
    with pytest.raises(ValueError, match="contiguous"):
        build_forecast(old + recent)
    invalid = [(period, 100.0, None) for period in _months(130)]
    invalid[-1] = (invalid[-1][0], float("nan"), None)
    with pytest.raises(ValueError, match="finite"):
        build_forecast(invalid)
