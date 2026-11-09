
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.entities import (
    AuditLog,
    CheckStatus,
    FraudAssessment,
    VerificationCheck,
)

from app.services.verification.contracts import (
    DocumentAnalysisResult,
    RiskAssessmentResult,
    VerificationOutcome,
)


class VerificationPersistenceError(RuntimeError):
    """Raised when verification persistence fails."""


def _map_outcome_to_status(
    outcome: VerificationOutcome,
) -> CheckStatus:
    mapping = {
        VerificationOutcome.PASS: CheckStatus.PASSED,
        VerificationOutcome.FAIL: CheckStatus.FAILED,
        VerificationOutcome.NEEDS_REVIEW: CheckStatus.NEEDS_REVIEW,
    }
    return mapping[outcome]


def save_document_analysis(
    db: Session,
    agent_id: uuid.UUID,
    result: DocumentAnalysisResult,
    actor_user_id: uuid.UUID | None = None,
) -> VerificationCheck:
    """
    Persist a document-analysis result and its audit event.

    The caller must supply an authorized agent ID.
    Raw extracted identity fields are not stored here.
    """

    check = VerificationCheck(
        agent_id=agent_id,
        check_type="document_analysis",
        status=_map_outcome_to_status(result.outcome),
        result_data={
            "document_id": str(result.document_id),
            "document_type": result.document_type,
            "analyzer_version": result.analyzer_version,
            "warnings_count": len(result.warnings),
            "outcome": result.outcome.value,
        },
    )

    audit = AuditLog(
        agent_id=agent_id,
        actor_user_id=actor_user_id,
        action="document_analysis_recorded",
        details={
            "document_id": str(result.document_id),
            "outcome": result.outcome.value,
        },
    )

    try:
        db.add(check)
        db.add(audit)
        db.commit()
        db.refresh(check)
        return check
    except Exception as exc:
        db.rollback()
        raise VerificationPersistenceError(
            "Failed to save document analysis."
        ) from exc


def save_risk_assessment(
    db: Session,
    result: RiskAssessmentResult,
    actor_user_id: uuid.UUID | None = None,
) -> FraudAssessment:
    """
    Persist an agent risk assessment and audit event.

    Detailed fraud evidence is not written to audit logs.
    """

    assessment = FraudAssessment(
        agent_id=result.agent_id,
        risk_score=result.risk_score,
        risk_level=result.risk_level.value,
        model_version=result.model_version,
    )

    audit = AuditLog(
        agent_id=result.agent_id,
        actor_user_id=actor_user_id,
        action="fraud_assessment_recorded",
        details={
            "risk_level": result.risk_level.value,
            "model_version": result.model_version,
            "indicator_count": len(result.indicators),
        },
    )

    try:
        db.add(assessment)
        db.add(audit)
        db.commit()
        db.refresh(assessment)
        return assessment
    except Exception as exc:
        db.rollback()
        raise VerificationPersistenceError(
            "Failed to save risk assessment."
        ) from exc
