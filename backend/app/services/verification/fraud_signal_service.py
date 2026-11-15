"""Trusted, data-minimized inputs for explainable fraud assessment.

This module deliberately works with counts, booleans, and provider outcome
categories. It never returns document checksums, identity fields, biometric
media, raw OCR, or raw provider decision payloads.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import CheckStatus, KYCDocument, VerificationCheck
from app.models.verification_case import VerificationCase
from app.services.kyc_upload_service import BIOMETRIC_DIDIT_CHECK_TYPE
from app.services.verification.risk_features import RiskFeatures


SIGNAL_WINDOW = timedelta(hours=24)
REPEATED_FAILURE_THRESHOLD = 3
VERIFICATION_FREQUENCY_THRESHOLD = 4
_FAILED_PROVIDER_OUTCOMES = frozenset({
    "declined",
    "rejected",
    "failed",
    "fail",
})


@dataclass(frozen=True)
class FraudSignalEvidence:
    """Counts and flags used to make the Phase 10 score reproducible."""

    duplicate_document_count: int = 0
    historical_failed_check_count: int = 0
    recent_verification_case_count: int = 0
    provider_kyc_declined: bool = False
    provider_liveness_failed: bool = False
    provider_identity_check_failed: bool = False

    def __post_init__(self) -> None:
        for name in (
            "duplicate_document_count",
            "historical_failed_check_count",
            "recent_verification_case_count",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer.")
        for name in (
            "provider_kyc_declined",
            "provider_liveness_failed",
            "provider_identity_check_failed",
        ):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be boolean.")

    def apply_to(self, base_features: RiskFeatures) -> RiskFeatures:
        """Combine trusted runtime evidence with non-PII document signals."""

        if not isinstance(base_features, RiskFeatures):
            raise TypeError("Expected validated RiskFeatures.")

        return replace(
            base_features,
            duplicate_document_confirmed=(
                self.duplicate_document_count > 0
            ),
            repeated_failures_confirmed=(
                self.historical_failed_check_count
                >= REPEATED_FAILURE_THRESHOLD
            ),
            unusual_verification_frequency=(
                self.recent_verification_case_count
                >= VERIFICATION_FREQUENCY_THRESHOLD
            ),
            provider_kyc_declined=self.provider_kyc_declined,
            provider_liveness_failed=self.provider_liveness_failed,
            provider_identity_check_failed=(
                self.provider_identity_check_failed
            ),
        )

    def indicator_evidence(self) -> dict[str, dict[str, int]]:
        """Return reviewer-safe evidence keyed by a triggered rule code."""

        evidence: dict[str, dict[str, int]] = {}
        if self.duplicate_document_count:
            evidence["DUPLICATE_DOCUMENT"] = {
                "matched_other_agent_documents": (
                    self.duplicate_document_count
                ),
            }
        if (
            self.historical_failed_check_count
            >= REPEATED_FAILURE_THRESHOLD
        ):
            evidence["REPEATED_FAILURES"] = {
                "historical_failed_checks": (
                    self.historical_failed_check_count
                ),
                "threshold": REPEATED_FAILURE_THRESHOLD,
                "window_hours": int(SIGNAL_WINDOW.total_seconds() // 3600),
            }
        if (
            self.recent_verification_case_count
            >= VERIFICATION_FREQUENCY_THRESHOLD
        ):
            evidence["UNUSUAL_VERIFICATION_FREQUENCY"] = {
                "recent_verification_cases": (
                    self.recent_verification_case_count
                ),
                "threshold": VERIFICATION_FREQUENCY_THRESHOLD,
                "window_hours": int(SIGNAL_WINDOW.total_seconds() // 3600),
            }
        return evidence


def _has_failed_provider_outcome(value: object) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.lower().replace("_", " ")
    return any(
        token.strip() in _FAILED_PROVIDER_OUTCOMES
        for token in normalized.split(",")
    )


def _provider_failure_flags(
    result_data: object,
) -> tuple[bool, bool, bool]:
    """Read only the minimized Phase 9 Didit summary, if one exists."""

    if not isinstance(result_data, dict):
        return False, False, False
    didit = result_data.get("didit")
    if not isinstance(didit, dict):
        return False, False, False
    kyc = didit.get("kyc")
    if not isinstance(kyc, dict):
        return False, False, False

    actions = kyc.get("actions")
    actions = actions if isinstance(actions, dict) else {}
    return (
        _has_failed_provider_outcome(kyc.get("status")),
        _has_failed_provider_outcome(actions.get("liveness")),
        _has_failed_provider_outcome(
            actions.get("id_verification")
        )
        or _has_failed_provider_outcome(actions.get("face_match")),
    )


def collect_trusted_fraud_signal_evidence(
    *,
    db: Session,
    agent_id: UUID,
    document_id: UUID,
    current_check_id: UUID | None,
    now: datetime | None = None,
) -> FraudSignalEvidence:
    """Collect backend-only counts and minimized KYC outcome categories."""

    if not isinstance(agent_id, UUID) or not isinstance(document_id, UUID):
        raise ValueError("Agent and document IDs must be UUIDs.")
    if current_check_id is not None and not isinstance(current_check_id, UUID):
        raise ValueError("Current check ID must be a UUID when provided.")

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Signal time must be timezone-aware.")
    window_start = now - SIGNAL_WINDOW

    checksum = db.execute(
        select(KYCDocument.sha256_checksum).where(
            KYCDocument.id == document_id,
            KYCDocument.agent_id == agent_id,
        )
    ).scalar_one_or_none()

    duplicate_document_count = 0
    if isinstance(checksum, str) and checksum:
        duplicate_document_count = int(
            db.execute(
                select(func.count(KYCDocument.id)).where(
                    KYCDocument.sha256_checksum == checksum,
                    KYCDocument.agent_id != agent_id,
                )
            ).scalar_one()
        )

    failed_check_conditions = [
        VerificationCheck.agent_id == agent_id,
        VerificationCheck.check_type == "document_analysis",
        VerificationCheck.status == CheckStatus.FAILED,
        VerificationCheck.created_at >= window_start,
    ]
    if current_check_id is not None:
        failed_check_conditions.append(
            VerificationCheck.id != current_check_id
        )

    historical_failed_check_count = int(
        db.execute(
            select(func.count(VerificationCheck.id)).where(
                *failed_check_conditions
            )
        ).scalar_one()
    )
    recent_verification_case_count = int(
        db.execute(
            select(func.count(VerificationCase.id)).where(
                VerificationCase.agent_id == agent_id,
                VerificationCase.created_at >= window_start,
            )
        ).scalar_one()
    )
    latest_didit_data = db.execute(
        select(VerificationCheck.result_data)
        .where(
            VerificationCheck.agent_id == agent_id,
            VerificationCheck.check_type == BIOMETRIC_DIDIT_CHECK_TYPE,
        )
        .order_by(VerificationCheck.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    (
        provider_kyc_declined,
        provider_liveness_failed,
        provider_identity_check_failed,
    ) = _provider_failure_flags(latest_didit_data)

    return FraudSignalEvidence(
        duplicate_document_count=duplicate_document_count,
        historical_failed_check_count=historical_failed_check_count,
        recent_verification_case_count=recent_verification_case_count,
        provider_kyc_declined=provider_kyc_declined,
        provider_liveness_failed=provider_liveness_failed,
        provider_identity_check_failed=provider_identity_check_failed,
    )


def assessment_key_for(
    *,
    agent_id: UUID,
    document_id: UUID,
    case_id: UUID | None,
    features: RiskFeatures,
    scoring_version: str,
) -> str:
    """Build an opaque idempotency key from safe assessment inputs."""

    if not isinstance(features, RiskFeatures):
        raise TypeError("Expected validated RiskFeatures.")
    payload = {
        "agent_id": str(agent_id),
        "document_id": str(document_id),
        "case_id": str(case_id) if case_id is not None else None,
        "features": asdict(features),
        "scoring_version": scoring_version,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
