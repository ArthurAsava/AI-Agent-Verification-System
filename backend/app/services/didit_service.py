from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.entities import Agent, AuditLog, CheckStatus, VerificationCheck
from app.services.kyc_upload_service import BIOMETRIC_DIDIT_CHECK_TYPE


DIDIT_PROVIDER = "didit"
DIDIT_HOSTED_WORKFLOW_MODE = "hosted_workflow"
DIDIT_SESSION_URL = "https://verification.didit.me/v3/session/"
_FINAL_SESSION_STATUSES = frozenset({"approved", "declined", "abandoned"})
_FEATURE_FIELDS = {
    "id_verifications": "id_verification",
    "liveness_checks": "liveness",
    "face_matches": "face_match",
}


class DiditError(RuntimeError):
    pass


class DiditConfigurationError(DiditError):
    pass


class DiditNotFoundError(DiditError):
    pass


class DiditConsentRequiredError(DiditError):
    pass


class DiditConflictError(DiditError):
    pass


class DiditSubmissionError(DiditError):
    pass


class DiditWebhookError(DiditError):
    pass


@dataclass(frozen=True)
class DiditConfig:
    api_key: str
    workflow_id: str
    webhook_secret: str
    webhook_previous_secret: str | None
    return_url: str
    environment: str


@dataclass(frozen=True)
class DiditSession:
    check_id: uuid.UUID
    session_id: str
    verification_url: str
    status: str


def _secret_value(value) -> str:
    return value.get_secret_value() if value is not None else ""


def _is_http_url(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def get_didit_config(settings: Settings | None = None) -> DiditConfig:
    settings = settings or get_settings()
    if not settings.DIDIT_ENABLED:
        raise DiditConfigurationError("Didit is not enabled for this environment.")

    api_key = _secret_value(settings.DIDIT_API_KEY)
    webhook_secret = _secret_value(settings.DIDIT_WEBHOOK_SECRET)
    if not (
        api_key
        and settings.DIDIT_WORKFLOW_ID
        and webhook_secret
        and settings.DIDIT_RETURN_URL
    ):
        raise DiditConfigurationError("Didit server configuration is incomplete.")
    if not _is_http_url(settings.DIDIT_RETURN_URL):
        raise DiditConfigurationError("Didit return URL must be an absolute HTTP(S) URL.")
    if (
        settings.DIDIT_ENVIRONMENT == "production"
        and not settings.DIDIT_RETURN_URL.startswith("https://")
    ):
        raise DiditConfigurationError(
            "Didit production return URL must use HTTPS."
        )

    previous_secret = _secret_value(settings.DIDIT_WEBHOOK_PREVIOUS_SECRET)
    return DiditConfig(
        api_key=api_key,
        workflow_id=settings.DIDIT_WORKFLOW_ID,
        webhook_secret=webhook_secret,
        webhook_previous_secret=previous_secret or None,
        return_url=settings.DIDIT_RETURN_URL,
        environment=settings.DIDIT_ENVIRONMENT,
    )


def _provider_user_id(agent_id: uuid.UUID) -> str:
    """Stable opaque identifier; no name, email, phone, or document data."""

    return f"salesmesh-{agent_id.hex}"


def _didit_result_data(check: VerificationCheck) -> dict[str, Any]:
    existing = (check.result_data or {}).get(DIDIT_PROVIDER)
    return dict(existing) if isinstance(existing, dict) else {}


def _set_didit_result_data(
    check: VerificationCheck,
    didit_data: dict[str, Any],
) -> None:
    result_data = dict(check.result_data or {})
    result_data[DIDIT_PROVIDER] = didit_data
    check.result_data = result_data


def _prepare_session(
    *,
    db: Session,
    user_id: uuid.UUID,
    biometric_consent: bool,
) -> tuple[VerificationCheck, DiditConfig]:
    if biometric_consent is not True:
        raise DiditConsentRequiredError(
            "Explicit consent is required before starting Didit verification."
        )
    config = get_didit_config()
    agent = db.execute(
        select(Agent).where(Agent.user_id == user_id)
    ).scalar_one_or_none()
    if agent is None:
        raise DiditNotFoundError("Agent profile not found.")

    existing = db.execute(
        select(VerificationCheck)
        .where(
            VerificationCheck.agent_id == agent.id,
            VerificationCheck.check_type == BIOMETRIC_DIDIT_CHECK_TYPE,
            VerificationCheck.status.in_(
                (CheckStatus.PENDING, CheckStatus.NEEDS_REVIEW)
            ),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if existing is not None:
        raise DiditConflictError(
            "A Didit verification is already in progress or awaiting review."
        )

    check = VerificationCheck(
        id=uuid.uuid4(),
        agent_id=agent.id,
        check_type=BIOMETRIC_DIDIT_CHECK_TYPE,
        status=CheckStatus.PENDING,
        result_data={
            "didit_provider_consent": True,
            "manual_review_required": True,
            DIDIT_PROVIDER: {
                "mode": DIDIT_HOSTED_WORKFLOW_MODE,
                "submission_status": "creating",
                "provider_user_id": _provider_user_id(agent.id),
                "environment": config.environment,
            },
        },
    )
    db.add(check)
    db.add(
        AuditLog(
            agent_id=agent.id,
            actor_user_id=user_id,
            action="didit_session_creation_started",
            details={
                "check_id": str(check.id),
                "provider": DIDIT_PROVIDER,
                "mode": DIDIT_HOSTED_WORKFLOW_MODE,
                "environment": config.environment,
            },
        )
    )
    db.commit()
    return check, config


async def _create_didit_session_request(
    *,
    config: DiditConfig,
    check: VerificationCheck,
) -> tuple[str, str]:
    payload = {
        "workflow_id": config.workflow_id,
        "vendor_data": _didit_result_data(check)["provider_user_id"],
        "callback": config.return_url,
        "callback_method": "both",
        "metadata": {"salesmesh_check_id": str(check.id)},
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                DIDIT_SESSION_URL,
                headers={"x-api-key": config.api_key},
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise DiditSubmissionError(
            "Didit did not accept the verification session."
        ) from exc

    if not isinstance(body, dict):
        raise DiditSubmissionError("Didit returned an invalid session response.")
    session_id = body.get("session_id")
    verification_url = body.get("url")
    if not isinstance(session_id, str) or not session_id:
        raise DiditSubmissionError("Didit did not return a session ID.")
    if not isinstance(verification_url, str) or not verification_url.startswith("https://"):
        raise DiditSubmissionError("Didit did not return a secure verification URL.")
    return session_id, verification_url


def _record_session_outcome(
    *,
    db: Session,
    check_id: uuid.UUID,
    session_id: str | None,
    success: bool,
) -> None:
    check = db.execute(
        select(VerificationCheck)
        .where(VerificationCheck.id == check_id)
        .with_for_update()
    ).scalar_one_or_none()
    if check is None:
        raise DiditNotFoundError("Didit verification record not found.")

    didit_data = _didit_result_data(check)
    didit_data["submission_status"] = "session_created" if success else "failed"
    if success and session_id is not None:
        didit_data["session_id"] = session_id
        didit_data["submitted_at"] = datetime.now(timezone.utc).isoformat()
        check.status = CheckStatus.NEEDS_REVIEW
    else:
        check.status = CheckStatus.FAILED
    _set_didit_result_data(check, didit_data)
    db.add(
        AuditLog(
            agent_id=check.agent_id,
            actor_user_id=None,
            action=(
                "didit_session_created" if success else "didit_session_creation_failed"
            ),
            details={
                "check_id": str(check.id),
                "provider": DIDIT_PROVIDER,
                "session_id": session_id,
            },
        )
    )
    db.commit()


async def start_didit_session(
    *,
    db: Session,
    user_id: uuid.UUID,
    biometric_consent: bool,
) -> DiditSession:
    """Create a hosted Didit flow without sending local biometric media."""

    check, config = _prepare_session(
        db=db,
        user_id=user_id,
        biometric_consent=biometric_consent,
    )
    try:
        session_id, verification_url = await _create_didit_session_request(
            config=config,
            check=check,
        )
    except DiditSubmissionError:
        _record_session_outcome(
            db=db,
            check_id=check.id,
            session_id=None,
            success=False,
        )
        raise

    _record_session_outcome(
        db=db,
        check_id=check.id,
        session_id=session_id,
        success=True,
    )
    return DiditSession(
        check_id=check.id,
        session_id=session_id,
        verification_url=verification_url,
        status="session_created",
    )


def _shorten_floats(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _shorten_floats(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_shorten_floats(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _valid_signature(
    *,
    payload: dict[str, Any],
    timestamp: str | None,
    signature: str | None,
    secret: str | None,
) -> bool:
    if not timestamp or not signature or not secret:
        return False
    try:
        if abs(time.time() - int(timestamp)) > 300:
            return False
    except ValueError:
        return False
    canonical = json.dumps(
        _shorten_floats(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    expected = hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


def _feature_statuses(payload: dict[str, Any]) -> dict[str, str]:
    decision = payload.get("decision")
    if not isinstance(decision, dict):
        return {}
    summaries: dict[str, str] = {}
    for field, name in _FEATURE_FIELDS.items():
        values = decision.get(field)
        if not isinstance(values, list):
            continue
        statuses = [
            str(item.get("status"))[:50]
            for item in values
            if isinstance(item, dict) and isinstance(item.get("status"), str)
        ]
        if statuses:
            summaries[name] = ", ".join(statuses[:3])[:100]
    return summaries


def record_didit_webhook(
    *,
    db: Session,
    payload: dict[str, Any],
    timestamp: str | None,
    signature: str | None,
    previous_signature: str | None,
) -> str:
    """Verify a Didit V2 webhook and persist only limited review evidence."""

    config = get_didit_config()
    current_valid = _valid_signature(
        payload=payload,
        timestamp=timestamp,
        signature=signature,
        secret=config.webhook_secret,
    )
    previous_valid = _valid_signature(
        payload=payload,
        timestamp=timestamp,
        signature=previous_signature,
        secret=config.webhook_previous_secret,
    )
    if not current_valid and not previous_valid:
        raise DiditWebhookError("Didit webhook signature is invalid.")
    if payload.get("webhook_type") != "status.updated":
        return "ignored"
    if payload.get("environment") != config.environment:
        raise DiditWebhookError("Didit webhook environment does not match.")

    session_id = payload.get("session_id")
    event_id = payload.get("event_id")
    status = payload.get("status")
    if not all(
        isinstance(value, str) and value
        for value in (session_id, event_id, status)
    ):
        raise DiditWebhookError("Didit webhook session fields are missing.")
    if len(session_id) > 100 or len(event_id) > 100 or len(status) > 50:
        raise DiditWebhookError("Didit webhook session fields are invalid.")

    check = db.execute(
        select(VerificationCheck).where(
            VerificationCheck.check_type == BIOMETRIC_DIDIT_CHECK_TYPE,
            VerificationCheck.result_data[DIDIT_PROVIDER]["session_id"].astext
            == session_id,
        )
    ).scalar_one_or_none()
    if check is None:
        raise DiditNotFoundError("Didit webhook session was not found.")

    didit_data = _didit_result_data(check)
    if didit_data.get("callback_event_id") == event_id:
        return "duplicate"

    session_status = status[:50]
    didit_data.update({
        "callback_event_id": event_id[:100],
        "callback_status": "received",
        "result": {
            "result_code": session_status,
            "result_text": None,
            "is_final": session_status.lower() in _FINAL_SESSION_STATUSES,
            "actions": _feature_statuses(payload),
        },
        "received_at": datetime.now(timezone.utc).isoformat(),
    })
    _set_didit_result_data(check, didit_data)
    db.add(
        AuditLog(
            agent_id=check.agent_id,
            actor_user_id=None,
            action="didit_result_received",
            details={
                "check_id": str(check.id),
                "provider": DIDIT_PROVIDER,
                "session_id": session_id,
                "event_id": event_id[:100],
                "session_status": session_status,
            },
        )
    )
    db.commit()
    return "accepted"
