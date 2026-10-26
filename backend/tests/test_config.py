
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


client = TestClient(app)


def test_application_name():
    settings = get_settings()

    assert settings.APP_NAME == "AI Agent Verification System"


def test_api_prefix():
    settings = get_settings()

    assert settings.API_V1_PREFIX == "/api/v1"


def test_openapi_documentation():
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "paths" in response.json()
    assert "/api/v1/health" in response.json()["paths"]
