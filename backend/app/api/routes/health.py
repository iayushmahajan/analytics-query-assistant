from typing import Literal

import httpx
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


def provider_status() -> str:
    if not settings.AI_API_URL or (settings.AI_PROVIDER == "groq" and not settings.AI_API_KEY):
        return "not_configured"
    models_url = settings.AI_API_URL.removesuffix("/chat/completions").rstrip("/") + "/models"
    try:
        headers = {"Authorization": f"Bearer {settings.AI_API_KEY}"} if settings.AI_PROVIDER == "groq" else None
        result = httpx.get(models_url, headers=headers, timeout=2) if headers else httpx.get(models_url, timeout=2)
        if result.status_code >= 400:
            return "unavailable"
        models = result.json().get("data", [])
        if settings.AI_PROVIDER == "groq":
            return "ok" if any(model.get("id") == settings.AI_MODEL for model in models) else "model_not_available"
        return "ok" if models else "model_not_loaded"
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        return "unavailable"


@router.get("/health", response_model=HealthResponse)
def health_check(response: Response):
    checks = {}
    for name, db in (("application_database", engine), ("analytics_database", analytics_engine)):
        try:
            with db.connect() as connection:
                connection.execute(
                    text(
                        "SELECT 1 FROM query_history LIMIT 0"
                        if name == "application_database"
                        else "SELECT geo_code FROM retail_observations LIMIT 0"
                    )
                )
                restricted = name != "analytics_database" or reader_is_restricted(connection)
            checks[name] = "ok" if restricted else "unsafe_role"
        except SQLAlchemyError:
            checks[name] = "unavailable"
    checks["provider"] = provider_status()
    healthy = all(checks[x] == "ok" for x in ("application_database", "analytics_database", "provider"))
    response.status_code = 200 if healthy else 503
    return HealthResponse(status="ok" if healthy else "degraded", **checks)
