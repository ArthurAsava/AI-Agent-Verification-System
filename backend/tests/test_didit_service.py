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
    get_didit_config,
    record_didit_webhook,
    start_didit_session,
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
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.side_effect = [
        agent,
        None,
        check,
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
