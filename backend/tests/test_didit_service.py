import hashlib
import hmac
import json
import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.models.entities import CheckStatus
from app.services import didit_service as service
from app.services.didit_service import (
    DiditConfig,
    DiditConsentRequiredError,
    DiditDecisionRetrievalError,
    DiditEligibilityError,
    get_didit_kyc_status,
    get_didit_config,
    record_didit_webhook,
    start_didit_session,
    sync_didit_kyc_decision,
)


def configured_settings():
    return Settings(
        DIDIT_ENABLED=True,
        DIDIT_API_KEY=SecretStr("didit-api-key-test"),
        DIDIT_WORKFLOW_ID="11111111-2222-3333-4444-555555555555",
        DIDIT_WEBHOOK_SECRET=SecretStr("webhook-secret-test"),
        DIDIT_RETURN_URL="http://localhost:3000/dashboard/verification",
        DIDIT_ENVIRONMENT="sandbox",
    )


def configured_didit() -> DiditConfig:
    return DiditConfig(
        api_key="didit-api-key-test",
        workflow_id="11111111-2222-3333-4444-555555555555",
        webhook_secret="webhook-secret-test",
        webhook_previous_secret=None,
        return_url="http://localhost:3000/dashboard/verification",
        environment="sandbox",
    )


def didit_signature(payload: dict, secret: str) -> str:
    canonical = json.dumps(
        service._shorten_floats(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def scalar_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def rows_result(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


def test_didit_config_keeps_secrets_server_only():
    config = get_didit_config(configured_settings())

    assert config.api_key == "didit-api-key-test"
    assert config.webhook_secret == "webhook-secret-test"
    assert config.environment == "sandbox"


@pytest.mark.asyncio
async def test_session_requires_explicit_provider_consent():
    with pytest.raises(DiditConsentRequiredError):
        await start_didit_session(
            db=MagicMock(),
            user_id=uuid.uuid4(),
            biometric_consent=False,
        )


@pytest.mark.asyncio
async def test_session_uses_hosted_flow_without_local_biometric_media(monkeypatch):
    agent_id = uuid.uuid4()
    user_id = uuid.uuid4()
    check = SimpleNamespace(
        id=uuid.uuid4(),
        agent_id=agent_id,
        status=CheckStatus.PENDING,
        result_data={
            "didit": {
                "mode": "hosted_workflow",
                "submission_status": "creating",
                "provider_user_id": f"salesmesh-{agent_id.hex}",
                "environment": "sandbox",
            }
        },
    )
    agent = SimpleNamespace(id=agent_id, user_id=user_id)
    submitted_document = SimpleNamespace(id=uuid.uuid4())
    db = MagicMock()
    db.execute.side_effect = [
        scalar_result(agent),
        rows_result(["national_id_front", "national_id_back"]),
        scalar_result(submitted_document),
        scalar_result(None),
        scalar_result(check),
    ]
    captured = {}

    monkeypatch.setattr(service, "get_didit_config", configured_didit)

    async def fake_create(*, config, check):
        captured["config"] = config
        captured["check"] = check
        return "session-123", "https://verify.didit.me/en/session/token"

    monkeypatch.setattr(service, "_create_didit_session_request", fake_create)

    result = await start_didit_session(
        db=db,
        user_id=user_id,
        biometric_consent=True,
    )

    assert result.session_id == "session-123"
    assert result.verification_url.startswith("https://verify.didit.me/")
    assert captured["check"].result_data["didit"]["provider_user_id"] == (
        f"salesmesh-{agent_id.hex}"
    )
    assert "selfie_content" not in captured["check"].result_data["didit"]
    assert check.status == CheckStatus.NEEDS_REVIEW


@pytest.mark.asyncio
async def test_session_requires_a_submitted_identity_document(monkeypatch):
    agent = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
    db = MagicMock()
    db.execute.side_effect = [
        scalar_result(agent),
        rows_result(["national_id_front", "national_id_back"]),
        scalar_result(None),
    ]
    monkeypatch.setattr(service, "get_didit_config", configured_didit)

    with pytest.raises(DiditEligibilityError):
        await start_didit_session(
            db=db,
            user_id=agent.user_id,
            biometric_consent=True,
        )


@pytest.mark.asyncio
async def test_session_requires_both_identity_documents(monkeypatch):
    agent = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
    db = MagicMock()
    db.execute.side_effect = [
        scalar_result(agent),
        rows_result(["national_id_front"]),
    ]
    monkeypatch.setattr(service, "get_didit_config", configured_didit)

    with pytest.raises(DiditEligibilityError, match="both sides"):
        await start_didit_session(
            db=db,
            user_id=agent.user_id,
            biometric_consent=True,
        )


def test_valid_didit_webhook_never_changes_biometric_check_status(monkeypatch):
    check = SimpleNamespace(
        id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        status=CheckStatus.NEEDS_REVIEW,
        result_data={"didit": {"session_id": "session-123"}},
    )
    payload = {
        "event_id": "event-123",
        "webhook_type": "status.updated",
        "timestamp": int(time.time()),
        "environment": "sandbox",
        "session_id": "session-123",
        "status": "Approved",
        "decision": {
            "liveness_checks": [{"status": "Approved"}],
            "face_matches": [{"status": "Approved"}],
        },
    }
    config = configured_didit()
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = check
    monkeypatch.setattr(service, "get_didit_config", lambda: config)

    status = record_didit_webhook(
        db=db,
        payload=payload,
        timestamp=str(payload["timestamp"]),
        signature=didit_signature(payload, config.webhook_secret),
        previous_signature=None,
    )

    assert status == "accepted"
    assert check.status == CheckStatus.NEEDS_REVIEW
    assert check.result_data["didit"]["result"]["actions"] == {
        "liveness": "Approved",
        "face_match": "Approved",
    }
    db.commit.assert_called_once()


def test_kyc_decision_minimization_never_persists_identity_fields():
    config = configured_didit()
    summary = service._minimize_kyc_decision(
        config=config,
        session_id="session-123",
        decision={
            "session_id": "session-123",
            "session_kind": "user",
            "environment": "sandbox",
            "status": "Approved",
            "id_verifications": [{
                "status": "Approved",
                "full_name": "Example Person",
                "date_of_birth": "1990-01-01",
                "document_number": "ABC123",
                "media_url": "https://provider.example/document",
            }],
            "liveness_checks": [{"status": "Approved"}],
            "face_matches": [{"status": "Approved"}],
            "ip_analyses": [{"status": "Approved"}],
        },
    )

    assert summary["status"] == "Approved"
    assert summary["is_final"] is True
    assert summary["actions"] == {
        "id_verification": "Approved",
        "liveness": "Approved",
        "face_match": "Approved",
        "ip_analysis": "Approved",
    }
    assert "Example Person" not in str(summary)
    assert "ABC123" not in str(summary)
    assert "media_url" not in str(summary)


@pytest.mark.asyncio
async def test_kyc_decision_retrieval_uses_the_server_only_provider_key(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "session_id": "session-123",
                "session_kind": "user",
                "environment": "sandbox",
                "status": "In Review",
                "id_verifications": [{"status": "Approved"}],
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, *, headers):
            captured["url"] = url
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr(service.httpx, "AsyncClient", lambda **kwargs: FakeClient())

    summary = await service._retrieve_didit_kyc_decision(
        config=configured_didit(),
        session_id="session-123",
    )

    assert captured["url"] == (
        "https://verification.didit.me/v3/session/session-123/decision/"
    )
    assert captured["headers"] == {
        "x-api-key": "didit-api-key-test",
        "Accept": "application/json",
    }
    assert summary["status"] == "In Review"
    assert summary["actions"] == {"id_verification": "Approved"}


@pytest.mark.asyncio
async def test_kyc_sync_persists_only_minimized_provider_evidence(monkeypatch):
    check = SimpleNamespace(
        id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        status=CheckStatus.NEEDS_REVIEW,
        result_data={"didit": {"session_id": "session-123"}},
    )
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = check
    monkeypatch.setattr(service, "get_didit_config", configured_didit)

    async def fake_retrieve(*, config, session_id):
        assert config == configured_didit()
        assert session_id == "session-123"
        return {
            "source": "session_decision",
            "session_kind": "user",
            "status": "Approved",
            "is_final": True,
            "actions": {"id_verification": "Approved"},
            "synced_at": "2026-11-15T00:00:00+00:00",
        }

    monkeypatch.setattr(service, "_retrieve_didit_kyc_decision", fake_retrieve)
    refresh_calls = []
    monkeypatch.setattr(
        service,
        "refresh_fraud_assessment_after_provider_sync",
        lambda **kwargs: refresh_calls.append(kwargs),
    )

    result = await sync_didit_kyc_decision(
        db=db,
        session_id="session-123",
        event_id="event-123",
    )

    assert result == "synced"
    assert check.status == CheckStatus.NEEDS_REVIEW
    assert check.result_data["didit"]["kyc"] == {
        "source": "session_decision",
        "session_kind": "user",
        "status": "Approved",
        "is_final": True,
        "actions": {"id_verification": "Approved"},
        "synced_at": "2026-11-15T00:00:00+00:00",
    }
    assert check.result_data["didit"]["result"]["result_text"] == (
        "Authoritative provider KYC decision synchronized."
    )
    assert refresh_calls == [{"db": db, "agent_id": check.agent_id}]
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_kyc_sync_is_idempotent_after_a_successful_event(monkeypatch):
    check = SimpleNamespace(
        id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        status=CheckStatus.NEEDS_REVIEW,
        result_data={
            "didit": {
                "session_id": "session-123",
                "kyc_decision_event_id": "event-123",
            }
        },
    )
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = check
    monkeypatch.setattr(service, "get_didit_config", configured_didit)

    async def should_not_retrieve(**kwargs):
        raise AssertionError("duplicate events must not retrieve the decision again")

    monkeypatch.setattr(service, "_retrieve_didit_kyc_decision", should_not_retrieve)

    assert await sync_didit_kyc_decision(
        db=db,
        session_id="session-123",
        event_id="event-123",
    ) == "already_synced"
    db.commit.assert_not_called()


def test_agent_kyc_status_excludes_session_identifier_and_provider_payload():
    agent = SimpleNamespace(id=uuid.uuid4())
    check = SimpleNamespace(
        id=uuid.uuid4(),
        status=CheckStatus.NEEDS_REVIEW,
        result_data={
            "didit": {
                "session_id": "provider-session-should-not-leak",
                "kyc": {
                    "status": "Approved",
                    "is_final": True,
                    "actions": {"liveness": "Approved"},
                    "synced_at": "2026-11-15T00:00:00+00:00",
                },
            }
        },
    )
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = agent
    db.execute.return_value.scalars.return_value.first.return_value = check

    status = get_didit_kyc_status(db=db, user_id=uuid.uuid4())

    assert status is not None
    assert status.provider_status == "Approved"
    assert status.actions == {"liveness": "Approved"}
    assert "provider-session" not in str(status)
