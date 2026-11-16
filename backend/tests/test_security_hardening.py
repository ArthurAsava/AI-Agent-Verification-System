import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import SlidingWindowRateLimiter
from app.main import app


def test_api_responses_have_security_headers():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in response.headers[
        "content-security-policy"
    ]


def test_explicit_frontend_origin_can_preflight_api_request():
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:3000"
    )


def test_untrusted_host_is_rejected_before_route_execution():
    with TestClient(app) as client:
        response = client.get("/", headers={"Host": "untrusted.example"})

    assert response.status_code == 400


def test_oversized_bearer_token_is_rejected_without_auth_request():
    token = "a." + ("b" * 8_192) + ".c"

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired access token"


def test_rate_limiter_slides_and_returns_retry_after():
    current_time = [1_000.0]
    limiter = SlidingWindowRateLimiter(
        limit=2,
        window_seconds=60,
        max_clients=2,
        clock=lambda: current_time[0],
    )

    assert limiter.allow("127.0.0.1") == (True, 0)
    assert limiter.allow("127.0.0.1") == (True, 0)
    assert limiter.allow("127.0.0.1") == (False, 60)

    current_time[0] += 60
    assert limiter.allow("127.0.0.1") == (True, 0)


def test_production_requires_https_and_transport_enforcement():
    with pytest.raises(ValidationError, match="ENFORCE_HTTPS"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            FRONTEND_URL="https://app.salesmesh.example",
            TRUSTED_HOSTS="api.salesmesh.example",
            ENFORCE_HTTPS=False,
            DIDIT_ENABLED=False,
        )

    settings = Settings(
        _env_file=None,
        APP_ENV="production",
        FRONTEND_URL="https://app.salesmesh.example",
        TRUSTED_HOSTS="api.salesmesh.example",
        ENFORCE_HTTPS=True,
        DIDIT_ENABLED=False,
    )

    assert settings.is_production is True


def test_cors_origin_and_host_lists_must_be_explicit():
    with pytest.raises(ValidationError, match="CORS_ALLOWED_ORIGINS"):
        Settings(_env_file=None, CORS_ALLOWED_ORIGINS="*")

    with pytest.raises(ValidationError, match="TRUSTED_HOSTS"):
        Settings(_env_file=None, TRUSTED_HOSTS="*")

    with pytest.raises(ValidationError, match="browser origins"):
        Settings(
            _env_file=None,
            CORS_ALLOWED_ORIGINS="https://app.salesmesh.example/path",
        )
