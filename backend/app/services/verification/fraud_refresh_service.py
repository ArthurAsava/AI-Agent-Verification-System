"""Refresh an open verification case after trusted provider evidence changes."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import AuditLog, FraudAssessment
from app.models.verification_case import VerificationCase, utc_now
from app.services.verification.contracts import RiskAssessmentResult
from app.services.verification.decision_contracts import CaseStatus
from app.services.verification.fraud_signal_service import (
    assessment_key_for,
    collect_trusted_fraud_signal_evidence,
)
from app.services.verification.persistence import save_risk_assessment
from app.services.verification.recommendation import build_recommendation
from app.services.verification.risk_contract_adapter import (
    to_risk_assessment_contract,
)
from app.services.verification.risk_engine import assess_risk
from app.services.verification.risk_features import RiskFeatures
from app.services.verification.risk_scoring import SCORING_VERSION


def _saved_signal_codes(signals: object) -> set[str]:
    if not isinstance(signals, list):
        return set()
    return {
        item["code"]
        for item in signals
        if isinstance(item, dict) and isinstance(item.get("code"), str)
    }


def base_features_from_assessment(
    assessment: FraudAssessment,
) -> RiskFeatures:
    """Rebuild Phase 10's safe document baseline from persisted rule codes."""

    codes = _saved_signal_codes(assessment.signals)
    identity_match = (
        "mismatch"
        if "IDENTITY_MISMATCH" in codes
        else "unknown"
        if "IDENTITY_UNKNOWN" in codes
        else "match"
    )
    document_quality = (
        "fail"
        if "DOCUMENT_QUALITY_FAILURE" in codes
        else "review"
        if "DOCUMENT_QUALITY_REVIEW" in codes
        else "unknown"
        if "DOCUMENT_QUALITY_UNKNOWN" in codes
        else "pass"
    )
    return RiskFeatures(
        identity_match=identity_match,
        document_quality=document_quality,
        missing_required_fields="MISSING_REQUIRED_FIELDS" in codes,
        conflicting_identity_fields=(
            "CONFLICTING_IDENTITY_FIELDS" in codes
        ),
    )


def refresh_fraud_assessment_after_provider_sync(
    *,
    db: Session,
    agent_id: UUID,
) -> FraudAssessment | None:
    """Reassess the latest open case after a signed provider decision sync.

    A provider callback can only update a recommendation for a case still
    awaiting review. It cannot approve, reject, or otherwise change an agent's
    access state.
    """

    previous = db.execute(
        select(FraudAssessment)
        .where(
            FraudAssessment.agent_id == agent_id,
            FraudAssessment.verification_case_id.is_not(None),
            FraudAssessment.model_version == SCORING_VERSION,
        )
        .order_by(FraudAssessment.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if previous is None or previous.verification_case_id is None:
        return None

    case = db.execute(
        select(VerificationCase).where(
            VerificationCase.id == previous.verification_case_id,
            VerificationCase.agent_id == agent_id,
        )
    ).scalar_one_or_none()
    if case is None:
        return None

    base_features = base_features_from_assessment(previous)
    evidence = collect_trusted_fraud_signal_evidence(
        db=db,
        agent_id=agent_id,
        document_id=case.document_id,
        current_check_id=None,
    )
    features = evidence.apply_to(base_features)
    risk = assess_risk(features)
    contract: RiskAssessmentResult = to_risk_assessment_contract(
        agent_id=agent_id,
        result=risk,
        indicator_evidence=evidence.indicator_evidence(),
    )
    assessment = save_risk_assessment(
        db=db,
        result=contract,
        commit=False,
        verification_case_id=case.id,
        assessment_key=assessment_key_for(
            agent_id=agent_id,
            document_id=case.document_id,
            case_id=case.id,
            features=features,
            scoring_version=risk.risk.scoring_version,
        ),
    )
    if assessment.id == previous.id:
        return assessment

    if case.status == CaseStatus.AWAITING_REVIEW.value:
        recommendation = build_recommendation(
            risk,
            document_analysis_passed=(
                base_features.identity_match == "match"
                and base_features.document_quality == "pass"
                and not base_features.missing_required_fields
                and not base_features.conflicting_identity_fields
            ),
        )
        previous_risk_level = case.risk_level
        case.recommendation = recommendation.recommendation.value
        case.risk_score = risk.risk.score
        case.risk_level = risk.risk.level
        case.scoring_version = risk.risk.scoring_version
        case.updated_at = utc_now()
        case.version += 1
        db.add(
            AuditLog(
                agent_id=agent_id,
                actor_user_id=None,
                action="fraud_assessment_refreshed_provider_signal",
                details={
                    "case_id": str(case.id),
                    "previous_risk_level": previous_risk_level,
                    "risk_level": risk.risk.level,
                    "indicator_codes": [
                        indicator.code for indicator in risk.indicators
                    ],
                },
            )
        )
        db.flush()

    return assessment
