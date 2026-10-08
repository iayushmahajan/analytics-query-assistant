"""Fixed, read-only market-intelligence views over the Eurostat retail dataset."""

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.db import analytics_engine

router = APIRouter(prefix="/retail", tags=["retail"])


class TrendPoint(BaseModel):
    period: date
    germany: float | None = None
    eu: float | None = None


class CategorySnapshot(BaseModel):
    code: str
    name: str
    period: date
    value: float
    monthly_change: float | None = None
    yearly_change: float | None = None
    volatility: float | None = None
    provisional: bool = False


class CountryRank(BaseModel):
    rank: int
    code: str
    name: str
    period: date
    value: float
    yearly_change: float
    provisional: bool = False


class AnomalyPoint(BaseModel):
    geography: str
    category: str
    period: date
    value: float
    monthly_change: float
    score: float
    direction: str
    provisional: bool = False


class RetailOverview(BaseModel):
    available: bool
    source: str = "Eurostat · sts_trtu_m"
    unit: str = "Seasonally adjusted volume index, 2021=100"
    source_updated_at: datetime | None = None
    source_sha256: str | None = None
    earliest_period: date | None = None
    latest_period: date | None = None
    observation_count: int = 0
    missing_cells: int = 0
    geography_count: int = 0
    category_count: int = 0
    provisional_count: int = 0
    germany_value: float | None = None
    germany_monthly_change: float | None = None
    germany_yearly_change: float | None = None
    germany_volatility: float | None = None
    germany_provisional: bool = False
    eu_value: float | None = None
    eu_yearly_change: float | None = None
    germany_rank: int | None = None
    ranked_country_count: int = 0
    history: list[TrendPoint] = Field(default_factory=list)
    categories: list[CategorySnapshot] = Field(default_factory=list)
    countries: list[CountryRank] = Field(default_factory=list)
    anomalies: list[AnomalyPoint] = Field(default_factory=list)


def _float(value: Decimal | None) -> float | None:
    return round(float(value), 3) if value is not None else None


def _provisional(status: str | None) -> bool:
    return bool(status and "p" in status.lower())


@router.get("/overview", response_model=RetailOverview)
def overview():
    with analytics_engine.connect() as connection:
        imported = connection.execute(text("""
            SELECT source_updated_at, source_sha256, earliest_period, latest_period,
                   observation_count, missing_cells, geography_count, category_count
            FROM retail_imports ORDER BY imported_at DESC LIMIT 1
        """)).one_or_none()
        if not imported:
            return RetailOverview(available=False)

        germany = connection.execute(text("""
            SELECT period, value, monthly_change, yearly_change, rolling_volatility, status
            FROM retail_observations
            WHERE geo_code = 'DE' AND category_code = 'G47'
            ORDER BY period DESC LIMIT 1
        """)).one_or_none()
        if not germany:
            return RetailOverview(available=False)
        latest_period = germany[0]
        eu = connection.execute(text("""
            SELECT value, yearly_change
            FROM retail_observations
            WHERE geo_code = 'EU27_2020' AND category_code = 'G47' AND period = :period
        """), {"period": latest_period}).one_or_none()
        history = connection.execute(text("""
            SELECT period,
                   MAX(value) FILTER (WHERE geo_code = 'DE') AS germany,
                   MAX(value) FILTER (WHERE geo_code = 'EU27_2020') AS eu
            FROM retail_observations
            WHERE category_code = 'G47' AND geo_code IN ('DE', 'EU27_2020')
            GROUP BY period ORDER BY period DESC LIMIT 60
        """)).all()
        categories = connection.execute(text("""
            SELECT DISTINCT ON (category_code)
                   category_code, category, period, value, monthly_change,
                   yearly_change, rolling_volatility, status
            FROM retail_observations
            WHERE geo_code = 'DE'
            ORDER BY category_code, period DESC
        """)).all()
        ranking_rows = connection.execute(text("""
            SELECT geo_code, geography, period, value, yearly_change, status
            FROM retail_observations
            WHERE category_code = 'G47' AND period = :period
              AND geo_code <> 'EU27_2020' AND yearly_change IS NOT NULL
            ORDER BY yearly_change DESC, geography
        """), {"period": latest_period}).all()
        anomalies = connection.execute(text("""
            SELECT geography, category, period, value, monthly_change, anomaly_score, status
            FROM retail_observations
            WHERE is_anomaly AND period >= :period - INTERVAL '24 months'
              AND monthly_change IS NOT NULL AND anomaly_score IS NOT NULL
            ORDER BY ABS(anomaly_score) DESC, period DESC LIMIT 12
        """), {"period": latest_period}).all()
        provisional_count = connection.execute(text("""
            SELECT COUNT(*) FROM retail_observations
            WHERE status IS NOT NULL AND LOWER(status) LIKE '%p%'
        """)).scalar_one()

    countries = [
        CountryRank(
            rank=index,
            code=row[0],
            name=row[1],
            period=row[2],
            value=_float(row[3]),
            yearly_change=_float(row[4]),
            provisional=_provisional(row[5]),
        )
        for index, row in enumerate(ranking_rows, 1)
    ]
    germany_rank = next((item.rank for item in countries if item.code == "DE"), None)
    return RetailOverview(
        available=True,
        source_updated_at=imported[0],
        source_sha256=imported[1],
        earliest_period=imported[2],
        latest_period=latest_period,
        observation_count=imported[4],
        missing_cells=imported[5],
        geography_count=imported[6],
        category_count=imported[7],
        provisional_count=provisional_count,
        germany_value=_float(germany[1]),
        germany_monthly_change=_float(germany[2]),
        germany_yearly_change=_float(germany[3]),
        germany_volatility=_float(germany[4]),
        germany_provisional=_provisional(germany[5]),
        eu_value=_float(eu[0]) if eu else None,
        eu_yearly_change=_float(eu[1]) if eu else None,
        germany_rank=germany_rank,
        ranked_country_count=len(countries),
        history=[TrendPoint(period=row[0], germany=_float(row[1]), eu=_float(row[2])) for row in reversed(history)],
        categories=[
            CategorySnapshot(
                code=row[0], name=row[1], period=row[2], value=_float(row[3]),
                monthly_change=_float(row[4]), yearly_change=_float(row[5]),
                volatility=_float(row[6]), provisional=_provisional(row[7]),
            )
            for row in categories
        ],
        countries=countries,
        anomalies=[
            AnomalyPoint(
                geography=row[0], category=row[1], period=row[2], value=_float(row[3]),
                monthly_change=_float(row[4]), score=_float(row[5]),
                direction="increase" if row[4] > 0 else "decrease",
                provisional=_provisional(row[6]),
            )
            for row in anomalies
        ],
    )
