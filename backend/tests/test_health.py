from unittest.mock import MagicMock

from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import health
from app.core.config import settings


def test_health_truthful_and_no_details(client, monkeypatch):
    healthy = MagicMock()
    unhealthy = MagicMock()
    unhealthy.connect.side_effect = SQLAlchemyError("secret connection details")
    monkeypatch.setattr(health, "engine", unhealthy)
    monkeypatch.setattr(health, "analytics_engine", healthy)
    monkeypatch.setattr(health, "reader_is_restricted", lambda connection: True)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert "secret" not in response.text
    monkeypatch.setattr(health, "engine", healthy)
    monkeypatch.setattr(settings, "GITHUB_MODELS_API_KEY", "")
    assert client.get("/health").status_code == 503
    monkeypatch.setattr(settings, "GITHUB_MODELS_API_KEY", "test-only")
    assert client.get("/health").status_code == 200
    monkeypatch.setattr(health, "reader_is_restricted", lambda connection: False)
    assert client.get("/health").json()["analytics_database"] == "unsafe_role"
