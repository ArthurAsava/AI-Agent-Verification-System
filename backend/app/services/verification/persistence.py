
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    Agent,
    AuditLog,
    CheckStatus,
    FraudAssessment,
    KYCDocument,
    VerificationCheck,
)

from app.services.verification.contracts import (
    DocumentAnalysisResult,
    RiskAssessmentResult,
    VerificationOutcome,
)


class VerificationPersistenceError(RuntimeError):
    """Raised when verification persistence fails."""


class VerificationIntegrityError(ValueError):
    """Raised when verification references are invalid."""


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
    Persist document analysis only when the document
    belongs to the specified agent.

    This function is intended for trusted internal callers.
    API-level authorization must be enforced separately.
    """
    try:
        document = db.execute(
            select(KYCDocument).where(
                KYCDocument.id == result.document_id,
                KYCDocument.agent_id == agent_id,
            )
        ).scalar_one_or_none()

        if document is None:
            raise VerificationIntegrityError(
                "Document does not belong to the agent "
                "or does not exist."
            )

        if document.document_type != result.document_type:
            raise VerificationIntegrityError(
                "Document type does not match the stored record."
            )

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

        db.add(check)
        db.add(audit)
        db.commit()
        db.refresh(check)

        return check

    except VerificationIntegrityError:
        db.rollback()
        raise

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
    Persist a risk assessment only for an existing agent.

    This function is intended for trusted internal callers.
    """
    try:
        agent = db.execute(
            select(Agent).where(
                Agent.id == result.agent_id
            )
        ).scalar_one_or_none()

        if agent is None:
            raise VerificationIntegrityError(
                "Agent does not exist."
            )

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

        db.add(assessment)
        db.add(audit)
        db.commit()
        db.refresh(assessment)

        return assessment

    except VerificationIntegrityError:
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()
        raise VerificationPersistenceError(
            "Failed to save risk assessment."
        ) from exc
