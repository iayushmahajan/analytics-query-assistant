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


class RetailForecast(Base):
    __tablename__ = "retail_forecasts"

    stock_code: Mapped[str] = mapped_column(String(30), primary_key=True)
    description: Mapped[str] = mapped_column(String(300))
    forecast_week: Mapped[date] = mapped_column(Date)
    training_cutoff: Mapped[date | None] = mapped_column(Date)
    predicted_units: Mapped[Decimal] = mapped_column(Numeric(12, 1))
    prediction_lower: Mapped[Decimal | None] = mapped_column(Numeric(12, 1))
    prediction_upper: Mapped[Decimal | None] = mapped_column(Numeric(12, 1))
    baseline_units: Mapped[Decimal] = mapped_column(Numeric(12, 1))
    model_mae: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    baseline_mae: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    test_mae: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    baseline_test_mae: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    test_wape: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    test_bias: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    interval_coverage: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    validation_weeks: Mapped[int | None] = mapped_column(Integer)
    test_weeks: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[str | None] = mapped_column(String(20))
    method: Mapped[str] = mapped_column(String(40))
    history: Mapped[list] = mapped_column(JSON)
    backtest: Mapped[list] = mapped_column(JSON)


class RetailImport(Base):
    __tablename__ = "retail_imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source: Mapped[str] = mapped_column(Text)
    source_sha256: Mapped[str] = mapped_column(String(64))
    archive_bytes: Mapped[int] = mapped_column(Integer)
    imported_lines: Mapped[int] = mapped_column(Integer)
    dropped_lines: Mapped[int] = mapped_column(Integer)
