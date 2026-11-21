import base64
import json
from types import SimpleNamespace
import uuid

import pytest

from app.core.auth import CurrentUser
from app.services import account_deletion_service as deletion_service
from app.services.account_deletion_service import (
    AccountDeletionForbiddenError,
    AccountDeletionPasswordError,
    AccountDeletionStorageError,
    delete_own_account,
    verify_account_password,
)
from app.services.storage_service import StorageOperationError


class FakeResult:
    def __init__(self, value=None):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeDb:
    def __init__(self, *, agent=None, documents=(), reviewer_values=()):
        self.agent = agent
        self.documents = list(documents)
        self.reviewer_values = list(reviewer_values)
        self.executed = []
        self.committed = False
        self.rolled_back = False

    def scalar(self, statement):
        if "verification_reviewers" in str(statement):
            return self.reviewer_values.pop(0)
        return self.agent

    def scalars(self, _statement):
        return SimpleNamespace(all=lambda: self.documents)

    def execute(self, statement, parameters=None):
        self.executed.append((str(statement), parameters))
        statement_text = str(statement)
        if "DELETE FROM auth.users" in statement_text:
            return FakeResult(uuid.uuid4())
        return FakeResult()

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class FakeStorage:
    def __init__(self, failure: Exception | None = None):
        self.failure = failure
        self.deleted = []

    async def delete(self, path, *, bucket=None):
        if self.failure:
            raise self.failure
        self.deleted.append((bucket, path))


class FakeAuthResponse:
    status_code = 200

    def __init__(self, user_id, session_id=None):
        self.user_id = user_id
        self.session_id = session_id or uuid.uuid4()

    def json(self):
        payload = base64.urlsafe_b64encode(
            json.dumps({"session_id": str(self.session_id)}).encode("utf-8")
        ).decode("utf-8").rstrip("=")
        return {
            "user": {"id": str(self.user_id)},
            "access_token": f"header.{payload}.signature",
        }


class FakeAuthClient:
    def __init__(self, response, calls):
        self.response = response
        self.calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url, *, headers, json):
        self.calls.append((url, headers, json))
        return self.response


@pytest.fixture
def user():
    return CurrentUser(id=uuid.uuid4(), email="regular@example.com")


@pytest.fixture
def password_verified(monkeypatch):
    async def fake_verify(_user, _password):
        return uuid.uuid4()

    monkeypatch.setattr(
        deletion_service,
        "verify_account_password",
        fake_verify,
    )


@pytest.mark.asyncio
async def test_deletion_removes_private_files_then_account_records(
    user,
    password_verified,
):
    agent_id = uuid.uuid4()
    db = FakeDb(
        agent=SimpleNamespace(id=agent_id),
        documents=(
            SimpleNamespace(
                storage_bucket="agent-kyc-documents",
                storage_path="agent-a/document-a/passport.pdf",
            ),
            SimpleNamespace(
                storage_bucket="agent-kyc-documents",
                storage_path="agent-a/document-b/selfie.jpg",
            ),
        ),
        # Both reviewer eligibility checks return no staff record.
        reviewer_values=(None, None),
    )
    storage = FakeStorage()

    await delete_own_account(
        db=db,
        storage=storage,
        user=user,
        password="correct-password",
    )

    assert storage.deleted == [
        ("agent-kyc-documents", "agent-a/document-a/passport.pdf"),
        ("agent-kyc-documents", "agent-a/document-b/selfie.jpg"),
    ]
    assert db.committed is True
    assert db.rolled_back is False
    executed_sql = "\n".join(statement for statement, _ in db.executed)
    assert "verification_cases" in executed_sql
    assert "audit_logs" in executed_sql
    assert "DELETE FROM agents" in executed_sql
    assert "DELETE FROM auth.sessions" in executed_sql
    assert "DELETE FROM auth.users" in executed_sql


@pytest.mark.asyncio
async def test_deletion_rolls_back_when_a_private_file_cannot_be_removed(
    user,
    password_verified,
):
    db = FakeDb(
        agent=SimpleNamespace(id=uuid.uuid4()),
        documents=(
            SimpleNamespace(
                storage_bucket="agent-kyc-documents",
                storage_path="agent-a/document-a/passport.pdf",
            ),
        ),
        reviewer_values=(None,),
    )
    storage = FakeStorage(StorageOperationError("storage unavailable"))

    with pytest.raises(AccountDeletionStorageError):
        await delete_own_account(
            db=db,
            storage=storage,
            user=user,
            password="correct-password",
        )

    assert db.rolled_back is True
    assert len(db.executed) == 1
    assert "DELETE FROM auth.sessions" in db.executed[0][0]


@pytest.mark.asyncio
async def test_reviewer_account_is_not_eligible_for_self_service_deletion(
    user,
    password_verified,
):
    db = FakeDb(reviewer_values=(user.id,))
    storage = FakeStorage()

    with pytest.raises(AccountDeletionForbiddenError):
        await delete_own_account(
            db=db,
            storage=storage,
            user=user,
            password="correct-password",
        )

    assert storage.deleted == []
    assert db.rolled_back is True


@pytest.mark.asyncio
async def test_password_confirmation_must_match_the_current_account(monkeypatch, user):
    calls = []

    monkeypatch.setattr(
        deletion_service,
        "get_settings",
        lambda: SimpleNamespace(
            SUPABASE_URL="https://example.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="publishable-key",
        ),
    )
    monkeypatch.setattr(
        deletion_service.httpx,
        "AsyncClient",
        lambda **_kwargs: FakeAuthClient(FakeAuthResponse(user.id), calls),
    )

    await verify_account_password(user, "correct-password")

    assert calls == [
        (
            "https://example.supabase.co/auth/v1/token?grant_type=password",
            {"apikey": "publishable-key", "Content-Type": "application/json"},
            {"email": "regular@example.com", "password": "correct-password"},
        )
    ]


@pytest.mark.asyncio
async def test_password_confirmation_rejects_another_authenticated_account(
    monkeypatch,
    user,
):
    monkeypatch.setattr(
        deletion_service,
        "get_settings",
        lambda: SimpleNamespace(
            SUPABASE_URL="https://example.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="publishable-key",
        ),
    )
    monkeypatch.setattr(
        deletion_service.httpx,
        "AsyncClient",
        lambda **_kwargs: FakeAuthClient(
            FakeAuthResponse(uuid.uuid4()),
            [],
        ),
    )

    with pytest.raises(AccountDeletionPasswordError):
        await verify_account_password(user, "correct-password")
