from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    question: str
    status: str
    row_count: int | None
    created_at: datetime
