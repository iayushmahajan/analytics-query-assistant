from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.analytics_security import reader_is_restricted
from app.core.config import settings
from app.core.db import analytics_engine, engine

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    api: str = "ok"
    application_database: str
    analytics_database: str
    provider: str


@router.get("/health", response_model=HealthResponse)
def health_check(response: Response):
    checks = {}
    for name, db in (("application_database", engine), ("analytics_database", analytics_engine)):
        try:
            with db.connect() as connection:
                connection.execute(text("SELECT 1 FROM query_history LIMIT 0" if name == "application_database" else "SELECT id FROM orders LIMIT 0"))
                restricted = name != "analytics_database" or reader_is_restricted(connection)
            checks[name] = "ok" if restricted else "unsafe_role"
        except SQLAlchemyError:
            checks[name] = "unavailable"
    checks["provider"] = "configured_not_probed" if settings.GITHUB_MODELS_API_KEY else "not_configured"
    healthy = all(checks[x] == "ok" for x in ("application_database", "analytics_database")) and bool(settings.GITHUB_MODELS_API_KEY)
    response.status_code = 200 if healthy else 503
    return HealthResponse(status="ok" if healthy else "degraded", **checks)
