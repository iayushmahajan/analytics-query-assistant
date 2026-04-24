from datetime import datetime

from pydantic import BaseModel


class HistoryItem(BaseModel):
    id: int
    question: str
    generated_sql: str
    explanation: str
    status: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }