import csv
import zipfile
from datetime import date, datetime, timedelta
from unittest.mock import Mock

import httpx
import pytest
from openpyxl import Workbook
from pydantic import ValidationError

from app.api.schemas.query import QueryPlan, QueryRequest
from app.core.config import settings
from app.scripts.import_retail import archive_sha256, convert_archive
from app.scripts.train_retail import build_forecasts
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


def test_forecast_uses_separate_chronological_validation_and_test_windows():
    start = date(2010, 12, 6)
    rows = [("A1", start + timedelta(weeks=i), 10 + i % 4) for i in range(40)]
    output = build_forecasts(rows, [("A1", "Product")], start + timedelta(weeks=39))
    forecast = output[0]
    assert forecast["forecast_week"] == start + timedelta(weeks=40)
    assert len(forecast["backtest"]) == 8
    assert forecast["model_mae"] >= 0 and forecast["baseline_mae"] >= 0
    assert forecast["test_mae"] >= 0 and forecast["baseline_test_mae"] >= 0
    assert 0 <= forecast["interval_coverage"] <= 1
    assert forecast["prediction_lower"] <= forecast["predicted_units"] <= forecast["prediction_upper"]
    assert forecast["validation_weeks"] == 8 and forecast["test_weeks"] == 8
    assert forecast["confidence"] in {"supported", "limited", "insufficient"}
    assert forecast["method"] in {"gradient_boosting", "four_week_average"}
    assert forecast["predicted_units"] >= 0
