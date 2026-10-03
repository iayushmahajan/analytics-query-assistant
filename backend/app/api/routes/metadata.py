from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.constants.metrics import CURRENCY, METRICS, Metric
from app.core.config import settings
from app.core.db import analytics_engine

router = APIRouter(tags=["metadata"])


class DatasetMetadata(BaseModel):
    name: str = "Northstar demo sales"
    synthetic: bool = True
    currency: str = CURRENCY
    date_start: date | None
    date_end: date | None
    order_count: int
    max_rows: int
    metrics: list[Metric]


@router.get("/metadata", response_model=DatasetMetadata)
def metadata():
    with analytics_engine.connect() as connection:
        row = connection.execute(text("SELECT MIN(order_date), MAX(order_date), COUNT(*) FROM orders")).one()
    return DatasetMetadata(date_start=row[0], date_end=row[1], order_count=row[2], max_rows=settings.MAX_SQL_ROWS, metrics=list(METRICS.values()))
