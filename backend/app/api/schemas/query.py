from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.constants.metrics import Metric, MetricId


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ClarificationTurn(Contract):
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=2000)


class QueryRequest(Contract):
    question: str = Field(min_length=1, max_length=2000)
    clarification: list[ClarificationTurn] = Field(default_factory=list, max_length=3)
    dataset: Literal["eurostat"] = "eurostat"


class QueryPlan(Contract):
    status: Literal["ready", "needs_clarification", "blocked"]
    sql: str | None = Field(default=None, max_length=20000)
    interpretation: str = Field(min_length=1, max_length=2000)
    metric: MetricId | None = None
    dimensions: list[str] = Field(default_factory=list, max_length=10)
    filters: list[str] = Field(default_factory=list, max_length=15)
    date_range: str = Field(default="All available dates", max_length=300)
    assumptions: list[str] = Field(default_factory=list, max_length=10)
    source_tables: list[str] = Field(default_factory=list, max_length=6)
    explanation: str = Field(min_length=1, max_length=2000)
    clarification_question: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def coherent(self):
        if self.status == "ready" and (not self.sql or self.metric is None):
            raise ValueError("Ready plans require SQL and a canonical metric")
        if self.status == "needs_clarification" and not self.clarification_question:
            raise ValueError("Clarification requires a question")
        if self.status != "ready" and self.sql is not None:
            raise ValueError("Non-ready plans cannot contain executable SQL")
        return self


class ResultAnalysis(Contract):
    answer: str = Field(min_length=1, max_length=2000)
    findings: list[str] = Field(default_factory=list, max_length=6)
    trends: list[str] = Field(default_factory=list, max_length=4)
    anomalies: list[str] = Field(default_factory=list, max_length=4)
    caveats: list[str] = Field(default_factory=list, max_length=6)
    follow_up_questions: list[str] = Field(default_factory=list, max_length=3)


class Timings(Contract):
    generation_ms: int = 0
    execution_ms: int = 0
    analysis_ms: int = 0
    total_ms: int = 0


class AppError(Contract):
    code: str
    message: str


class QueryResponse(Contract):
    id: int | None = None
    request_id: str
    question: str
    dataset: Literal["eurostat"] = "eurostat"
    clarification: list[ClarificationTurn] = Field(default_factory=list)
    status: Literal["success", "needs_clarification", "blocked", "failed"]
    plan: QueryPlan | None = None
    metric_definition: Metric | None = None
    generated_sql: str = ""
    columns: list[str] = Field(default_factory=list)
    rows: list[list[str | int | float | bool | None]] = Field(default_factory=list)
    row_count: int = 0
    possibly_truncated: bool = False
    analysis: ResultAnalysis | None = None
    warnings: list[str] = Field(default_factory=list)
    timings: Timings = Field(default_factory=Timings)
    error: AppError | None = None
    created_at: datetime
