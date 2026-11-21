
from datetime import datetime, timezone
import uuid

from fastapi.testclient import TestClient

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db
from app.main import app
from app.api.routes import auth as auth_routes
from app.services.account_deletion_service import AccountDeletionPasswordError


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


def test_account_sessions_requires_token():
    response = client.get("/api/v1/auth/sessions")

    assert response.status_code == 401


def test_account_capabilities_requires_token():
    response = client.get("/api/v1/auth/capabilities")

    assert response.status_code == 401


def test_account_deletion_requires_token():
    response = client.post(
        "/api/v1/auth/delete-account",
        json={"password": "correct-password"},
    )

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


def test_account_capabilities_use_the_server_managed_admin_role():
    user_id = uuid.uuid4()

    class FakeResult:
        def scalar_one_or_none(self):
            return user_id

    class FakeDb:
        def execute(self, _statement):
            return FakeResult()

    def fake_user():
        return CurrentUser(id=user_id, email="admin@example.com")

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db] = lambda: FakeDb()

    try:
        response = client.get("/api/v1/auth/capabilities")

        assert response.status_code == 200
        assert response.json() == {"is_admin": True}
    finally:
        app.dependency_overrides.clear()


def test_account_sessions_only_marks_the_validated_current_session():
    user_id = uuid.uuid4()
    current_session_id = uuid.uuid4()
    other_session_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    class FakeResult:
        def mappings(self):
            return [
                {
                    "id": current_session_id,
                    "created_at": now,
                    "last_active_at": now,
                    "expires_at": None,
                    "user_agent": "Verity Browser\n  1.0",
                },
                {
                    "id": other_session_id,
                    "created_at": now,
                    "last_active_at": now,
                    "expires_at": None,
                    "user_agent": None,
                },
            ]

    class FakeDb:
        def execute(self, _statement, parameters):
            assert parameters == {"user_id": user_id}
            return FakeResult()

    def fake_user():
        return CurrentUser(
            id=user_id,
            email="test@example.com",
            session_id=current_session_id,
        )

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db] = lambda: FakeDb()

    try:
        response = client.get("/api/v1/auth/sessions")

        assert response.status_code == 200
        assert response.json() == [
            {
                "id": str(current_session_id),
                "created_at": now.isoformat().replace("+00:00", "Z"),
                "last_active_at": now.isoformat().replace("+00:00", "Z"),
                "expires_at": None,
                "user_agent": "Verity Browser 1.0",
                "is_current": True,
            },
            {
                "id": str(other_session_id),
                "created_at": now.isoformat().replace("+00:00", "Z"),
                "last_active_at": now.isoformat().replace("+00:00", "Z"),
                "expires_at": None,
                "user_agent": None,
                "is_current": False,
            },
        ]
    finally:
        app.dependency_overrides.clear()


def test_account_deletion_passes_confirmation_to_service(monkeypatch):
    user_id = uuid.uuid4()
    captured = {}

    def fake_user():
        return CurrentUser(id=user_id, email="test@example.com")

    async def fake_delete_own_account(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        auth_routes,
        "delete_own_account",
        fake_delete_own_account,
    )
    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[
        auth_routes.get_account_deletion_storage
    ] = lambda: object()

    try:
        response = client.post(
            "/api/v1/auth/delete-account",
            json={"password": "correct-password"},
        )

        assert response.status_code == 200
        assert response.json() == {"deleted": True}
        assert captured["user"].id == user_id
        assert captured["password"] == "correct-password"
    finally:
        app.dependency_overrides.clear()


def test_account_deletion_rejects_wrong_password(monkeypatch):
    user_id = uuid.uuid4()

    def fake_user():
        return CurrentUser(id=user_id, email="test@example.com")

    async def fake_delete_own_account(**_kwargs):
        raise AccountDeletionPasswordError("Password is incorrect.")

    monkeypatch.setattr(
        auth_routes,
        "delete_own_account",
        fake_delete_own_account,
    )
    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[
        auth_routes.get_account_deletion_storage
    ] = lambda: object()

    try:
        response = client.post(
            "/api/v1/auth/delete-account",
            json={"password": "incorrect-password"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Password is incorrect."
    finally:
        app.dependency_overrides.clear()
