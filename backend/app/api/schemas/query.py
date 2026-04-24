from datetime import datetime

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Natural language business question")


class QueryResponse(BaseModel):
    id: int
    question: str
    generated_sql: str
    explanation: str
    status: str
    created_at: datetime