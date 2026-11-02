
import uuid

from fastapi.testclient import TestClient

from app.core.auth import CurrentUser, get_current_user
from app.main import app


client = TestClient(app)


def test_auth_me_requires_token():
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_agent_registration_requires_token():
    response = client.post(
        "/api/v1/agents/register",
        json={
            "first_name": "Test",
            "last_name": "Agent",
        },
    )

    assert response.status_code == 401


def test_agent_profile_requires_token():
    response = client.get("/api/v1/agents/me")

    assert response.status_code == 401


def test_agent_update_requires_token():
    response = client.patch(
        "/api/v1/agents/me",
        json={"first_name": "Updated"},
    )

    assert response.status_code == 401


def test_authenticated_identity():
    user_id = uuid.uuid4()

    def fake_user():
        return CurrentUser(
            id=user_id,
            email="test@example.com",
        )

    app.dependency_overrides[get_current_user] = fake_user

    try:
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 200
        assert response.json()["id"] == str(user_id)
        assert response.json()["email"] == "test@example.com"
    finally:
        app.dependency_overrides.clear()
