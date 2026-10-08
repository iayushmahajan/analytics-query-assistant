from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Date, DateTime, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RetailLine(Base):
    __tablename__ = "retail_lines"
    __table_args__ = (
        Index("ix_retail_lines_date", "invoice_date"),
        Index("ix_retail_lines_product_date", "stock_code", "invoice_date"),
        Index("ix_retail_lines_invoice", "invoice_no"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_no: Mapped[str] = mapped_column(String(20))
    stock_code: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(String(300))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    invoice_date: Mapped[datetime] = mapped_column(DateTime)
    country: Mapped[str] = mapped_column(String(100))
    is_sale: Mapped[bool] = mapped_column(Boolean)


class RetailImport(Base):
    __tablename__ = "retail_imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source: Mapped[str] = mapped_column(Text)
    source_sha256: Mapped[str] = mapped_column(String(64))
    archive_bytes: Mapped[int] = mapped_column(Integer)
    imported_lines: Mapped[int] = mapped_column(Integer)
    dropped_lines: Mapped[int] = mapped_column(Integer)


class MarketObservation(Base):
    __tablename__ = "market_observations"

    period: Mapped[date] = mapped_column(Date, primary_key=True)
    value: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    status: Mapped[str | None] = mapped_column(String(20))


class MarketImport(Base):
    __tablename__ = "market_imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source: Mapped[str] = mapped_column(Text)
    source_sha256: Mapped[str] = mapped_column(String(64))
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observation_count: Mapped[int] = mapped_column(Integer)
    missing_periods: Mapped[int] = mapped_column(Integer)
    latest_period: Mapped[date] = mapped_column(Date)
    latest_status: Mapped[str | None] = mapped_column(String(20))


class MarketForecast(Base):
    __tablename__ = "market_forecasts"

    geo_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    target_period: Mapped[date] = mapped_column(Date)
    training_cutoff: Mapped[date] = mapped_column(Date)
    predicted_index: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    prediction_lower: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    prediction_upper: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    baseline_index: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    method: Mapped[str] = mapped_column(String(40))
    baseline_method: Mapped[str] = mapped_column(String(40))
    validation_mae: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    baseline_validation_mae: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    test_mae: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    baseline_test_mae: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    test_wape: Mapped[Decimal] = mapped_column(Numeric(8, 5))
    test_bias: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    interval_coverage: Mapped[Decimal] = mapped_column(Numeric(8, 5))
    confidence: Mapped[str] = mapped_column(String(20))
    validation_months: Mapped[int] = mapped_column(Integer)
    test_months: Mapped[int] = mapped_column(Integer)
    latest_observation_status: Mapped[str | None] = mapped_column(String(20))
    history: Mapped[list] = mapped_column(JSON)
    backtest: Mapped[list] = mapped_column(JSON)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
