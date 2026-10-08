"""Bounded, read-only dashboard data for the separately imported UCI dataset."""

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.db import analytics_engine

router = APIRouter(prefix="/retail", tags=["retail"])


class MonthlyPoint(BaseModel):
    month: str
    gross_sales: float
    units: int


class RankedPoint(BaseModel):
    name: str
    gross_sales: float
    units: int


class RetailOverview(BaseModel):
    available: bool
    source: str = "UCI Online Retail · CC BY 4.0"
    currency: str = "GBP"
    start: date | None = None
    end: date | None = None
    source_lines: int = 0
    sale_lines: int = 0
    excluded_lines: int = 0
    sales_invoices: int = 0
    gross_sales: float = 0
    units: int = 0
    months: list[MonthlyPoint] = Field(default_factory=list)
    products: list[RankedPoint] = Field(default_factory=list)
    countries: list[RankedPoint] = Field(default_factory=list)
    imported_at: datetime | None = None
    source_sha256: str | None = None
    dropped_lines: int = 0


def _money(value: Decimal | None) -> float:
    return round(float(value or 0), 2)


@router.get("/overview", response_model=RetailOverview)
def overview():
    with analytics_engine.connect() as connection:
        total = connection.execute(text("""
            SELECT MIN(invoice_date)::date, MAX(invoice_date)::date, COUNT(*),
                   COUNT(*) FILTER (WHERE is_sale),
                   COUNT(DISTINCT invoice_no) FILTER (WHERE is_sale),
                   SUM(quantity * unit_price) FILTER (WHERE is_sale),
                   SUM(quantity) FILTER (WHERE is_sale)
            FROM retail_lines
        """)).one()
        imported = connection.execute(text("""
            SELECT imported_at, source_sha256, dropped_lines
            FROM retail_imports ORDER BY imported_at DESC LIMIT 1
        """)).one_or_none()
        if not total[2]:
            return RetailOverview(available=False)
        months = connection.execute(text("""
            SELECT to_char(date_trunc('month', invoice_date), 'YYYY-MM'),
                   SUM(quantity * unit_price), SUM(quantity)
            FROM retail_lines WHERE is_sale
            GROUP BY 1 ORDER BY 1
        """)).all()
        products = connection.execute(text("""
            SELECT MIN(description), SUM(quantity * unit_price), SUM(quantity)
            FROM retail_lines WHERE is_sale
            GROUP BY stock_code ORDER BY 2 DESC LIMIT 8
        """)).all()
        countries = connection.execute(text("""
            SELECT country, SUM(quantity * unit_price), SUM(quantity)
            FROM retail_lines WHERE is_sale
            GROUP BY country ORDER BY 2 DESC LIMIT 8
        """)).all()
    return RetailOverview(
        available=True, start=total[0], end=total[1], source_lines=total[2],
        sale_lines=total[3], excluded_lines=total[2] - total[3],
        sales_invoices=total[4], gross_sales=_money(total[5]), units=total[6] or 0,
        months=[MonthlyPoint(month=m, gross_sales=_money(v), units=u) for m, v, u in months],
        products=[RankedPoint(name=n, gross_sales=_money(v), units=u) for n, v, u in products],
        countries=[RankedPoint(name=n, gross_sales=_money(v), units=u) for n, v, u in countries],
        imported_at=imported[0] if imported else None,
        source_sha256=imported[1] if imported else None,
        dropped_lines=imported[2] if imported else 0,
    )


class ForecastPoint(BaseModel):
    period: date
    actual: float | None = None
    predicted: float | None = None


class MarketForecast(BaseModel):
    available: bool
    geo_code: str = "DE"
    geography: str = "Germany"
    indicator: str = "Seasonally and calendar adjusted retail trade volume index"
    unit: str = "Index, 2021=100"
    source: str = "Eurostat · sts_trtu_m"
    source_updated_at: datetime | None = None
    source_sha256: str | None = None
    missing_periods: int = 0
    target_period: date | None = None
    training_cutoff: date | None = None
    predicted_index: float | None = None
    prediction_lower: float | None = None
    prediction_upper: float | None = None
    baseline_index: float | None = None
    method: str | None = None
    baseline_method: str | None = None
    ml_validation_mae: float | None = None
    baseline_validation_mae: float | None = None
    test_mae: float | None = None
    baseline_test_mae: float | None = None
    test_wape: float | None = None
    test_bias: float | None = None
    interval_coverage: float | None = None
    confidence: str | None = None
    validation_months: int | None = None
    test_months: int | None = None
    latest_observation_status: str | None = None
    history: list[ForecastPoint] = Field(default_factory=list)
    backtest: list[ForecastPoint] = Field(default_factory=list)
    trained_at: datetime | None = None


@router.get("/market-forecast", response_model=MarketForecast)
def market_forecast():
    with analytics_engine.connect() as connection:
        imported = connection.execute(text("""
            SELECT source_updated_at, source_sha256, missing_periods
            FROM market_imports ORDER BY imported_at DESC LIMIT 1
        """)).one_or_none()
        row = connection.execute(text("""
            SELECT geo_code, target_period, training_cutoff, predicted_index,
                   prediction_lower, prediction_upper, baseline_index, method,
                   baseline_method, validation_mae AS ml_validation_mae, baseline_validation_mae,
                   test_mae, baseline_test_mae, test_wape, test_bias,
                   interval_coverage, confidence, validation_months, test_months,
                   latest_observation_status, history, backtest, trained_at
            FROM market_forecasts WHERE geo_code = 'DE'
        """)).mappings().one_or_none()
    provenance = {
        "source_updated_at": imported[0] if imported else None,
        "source_sha256": imported[1] if imported else None,
        "missing_periods": imported[2] if imported else 0,
    }
    if not row:
        return MarketForecast(available=False, **provenance)
    return MarketForecast.model_validate({"available": True, **provenance, **dict(row)})
