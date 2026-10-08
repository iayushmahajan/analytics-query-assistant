from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RetailObservation(Base):
    __tablename__ = "retail_observations"
    __table_args__ = (
        Index("ix_retail_observations_period", "period"),
        Index("ix_retail_observations_category_period", "category_code", "period"),
        Index("ix_retail_observations_anomaly", "is_anomaly", "period"),
        CheckConstraint("value > 0", name="ck_retail_observation_value"),
    )

    geo_code: Mapped[str] = mapped_column(String(12), primary_key=True)
    geography: Mapped[str] = mapped_column(String(100))
    category_code: Mapped[str] = mapped_column(String(30), primary_key=True)
    category: Mapped[str] = mapped_column(String(200))
    period: Mapped[date] = mapped_column(Date, primary_key=True)
    value: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    status: Mapped[str | None] = mapped_column(String(20))
    monthly_change: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    yearly_change: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    rolling_volatility: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    anomaly_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())


class RetailImport(Base):
    __tablename__ = "retail_imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source: Mapped[str] = mapped_column(Text)
    source_sha256: Mapped[str] = mapped_column(String(64))
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observation_count: Mapped[int] = mapped_column(Integer)
    missing_cells: Mapped[int] = mapped_column(Integer)
    earliest_period: Mapped[date] = mapped_column(Date)
    latest_period: Mapped[date] = mapped_column(Date)
    geography_count: Mapped[int] = mapped_column(Integer)
    category_count: Mapped[int] = mapped_column(Integer)
