from fastapi.testclient import TestClient

from app.main import app
from app.services.didit_service import DiditConfigurationError


def test_didit_session_requires_agent_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/biometric/didit/sessions",
            json={"biometric_consent": True},
        )

    assert response.status_code == 401


def test_didit_webhook_rejects_unconfigured_provider(monkeypatch):
    def unavailable(**kwargs):
        raise DiditConfigurationError("Provider unavailable")

    monkeypatch.setattr(
        "app.api.routes.didit.record_didit_webhook",
        unavailable,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/biometric/didit/webhook",
            headers={"x-timestamp": "1", "x-signature-v2": "untrusted"},
            json={"webhook_type": "status.updated"},
        )

    assert response.status_code == 503
