from unittest.mock import MagicMock, Mock

import httpx
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
    monkeypatch.setattr(health, "provider_status", lambda: "ok")
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert "secret" not in response.text
    monkeypatch.setattr(health, "engine", healthy)
    monkeypatch.setattr(health, "provider_status", lambda: "not_configured")
    assert client.get("/health").status_code == 503
    monkeypatch.setattr(health, "provider_status", lambda: "ok")
    assert client.get("/health").status_code == 200
    monkeypatch.setattr(health, "reader_is_restricted", lambda connection: False)
    assert client.get("/health").json()["analytics_database"] == "unsafe_role"


def test_provider_status_probes_loaded_models(monkeypatch):
    monkeypatch.setattr(settings, "AI_API_URL", "")
    assert health.provider_status() == "not_configured"

    monkeypatch.setattr(settings, "AI_API_URL", "http://provider.test/v1/chat/completions")
    get = Mock(return_value=httpx.Response(200, json={"data": [{"id": "phi-4-mini"}]}))
    monkeypatch.setattr(health.httpx, "get", get)
    assert health.provider_status() == "ok"
    get.assert_called_once_with("http://provider.test/v1/models", timeout=2)

    get.return_value = httpx.Response(200, json={"data": []})
    assert health.provider_status() == "model_not_loaded"
    get.side_effect = httpx.ConnectError("offline")
    assert health.provider_status() == "unavailable"
