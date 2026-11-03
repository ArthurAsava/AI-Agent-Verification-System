
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_onboarding_requires_authentication():
    response = client.get(
        "/api/v1/onboarding/me"
    )

    assert response.status_code == 401


def test_onboarding_update_requires_authentication():
    response = client.patch(
        "/api/v1/onboarding/me",
        json={"county": "Nairobi"},
    )

    assert response.status_code == 401


def test_kyc_requirements_require_authentication():
    response = client.get(
        "/api/v1/kyc/requirements"
    )

    assert response.status_code == 401
