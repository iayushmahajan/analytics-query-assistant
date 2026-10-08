from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class HistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    question: str
    dataset: Literal["eurostat"] = "eurostat"
    status: str
    row_count: int | None
    created_at: datetime
