from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.customer import Customer


class Country(Base):
    __tablename__ = "countries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False)

    customers: Mapped[list[Customer]] = relationship(
        "Customer",
        back_populates="country",
        cascade="all, delete-orphan",
    )