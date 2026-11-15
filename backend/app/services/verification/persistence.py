
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
from app.models.verification_case import VerificationCase

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
    """
    Convert a document analysis outcome into
    the corresponding database check status.
    """
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
    *,
    commit: bool = True,
) -> VerificationCheck:
    """
    Persist a document analysis result.

    SECURITY:
    The document must belong to the specified agent.
    API-level authorization is enforced separately.

    TRANSACTION CONTROL:
    commit=True:
        Commit the document analysis and audit event.

    commit=False:
        Flush changes without committing, allowing
        a higher-level orchestrator to manage the
        transaction.
    """
    try:
        # 1. Verify document ownership.
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

        # 2. Verify document type consistency.
        if document.document_type != result.document_type:
            raise VerificationIntegrityError(
                "Document type does not match the stored record."
            )

        # 3. Create the document verification record.
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

        # 4. Create the corresponding audit record.
        audit = AuditLog(
            agent_id=agent_id,
            actor_user_id=actor_user_id,
            action="document_analysis_recorded",
            details={
                "document_id": str(result.document_id),
                "outcome": result.outcome.value,
            },
        )

        # 5. Add both records to the transaction.
        db.add(check)
        db.add(audit)

        # 6. Commit or defer the transaction.
        if commit:
            db.commit()
            db.refresh(check)
        else:
            db.flush()

        # 7. Return the saved verification check.
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
    *,
    commit: bool = True,
    verification_case_id: uuid.UUID | None = None,
    assessment_key: str | None = None,
) -> FraudAssessment:
    """
    Persist a data-minimized, explainable fraud-risk assessment.

    SECURITY:
    The assessment must reference an existing agent.
    API-level authorization is enforced separately.

    TRANSACTION CONTROL:
    commit=True:
        Commit the fraud assessment and audit event.

    commit=False:
        Flush changes without committing, allowing
        a higher-level orchestrator to manage the
        transaction.
    """
    phase_ten_key_supplied = assessment_key is not None
    if assessment_key is None:
        # Compatibility for callers predating the Phase 10 idempotent
        # pipeline. The Phase 10 orchestrator always supplies a stable key.
        assessment_key = f"legacy-{uuid.uuid4().hex}"
    if (
        not isinstance(assessment_key, str)
        or not 1 <= len(assessment_key) <= 64
    ):
        raise ValueError(
            "Assessment key must be a non-empty value up to 64 characters."
        )

    try:
        # 1. Verify that the agent exists.
        agent = db.execute(
            select(Agent).where(
                Agent.id == result.agent_id
            )
        ).scalar_one_or_none()

        if agent is None:
            raise VerificationIntegrityError(
                "Agent does not exist."
            )

        if verification_case_id is not None:
            case = db.execute(
                select(VerificationCase).where(
                    VerificationCase.id == verification_case_id,
                    VerificationCase.agent_id == result.agent_id,
                )
            ).scalar_one_or_none()
            if case is None:
                raise VerificationIntegrityError(
                    "Verification case does not belong to the agent "
                    "or does not exist."
                )

        # A repeated request with exactly the same safe assessment inputs is
        # intentionally a no-op. This avoids duplicate review evidence.
        if phase_ten_key_supplied:
            existing = db.execute(
                select(FraudAssessment).where(
                    FraudAssessment.assessment_key == assessment_key
                )
            ).scalar_one_or_none()
            if existing is not None:
                if existing.agent_id != result.agent_id:
                    raise VerificationIntegrityError(
                        "Assessment key belongs to another agent."
                    )
                return existing

        # 2. Create the fraud assessment record. Indicator evidence is
        # already data-minimized by the fraud signal service.
        assessment = FraudAssessment(
            agent_id=result.agent_id,
            risk_score=result.risk_score,
            risk_level=result.risk_level.value,
            model_version=result.model_version,
            verification_case_id=verification_case_id,
            assessment_key=assessment_key,
            signals=[
                indicator.model_dump(mode="json")
                for indicator in result.indicators
            ],
            requires_review=result.requires_review,
        )

        # 3. Create the corresponding audit record.
        audit = AuditLog(
            agent_id=result.agent_id,
            actor_user_id=actor_user_id,
            action="fraud_assessment_recorded",
            details={
                "risk_level": result.risk_level.value,
                "model_version": result.model_version,
                "indicator_count": len(result.indicators),
                "indicator_codes": [
                    indicator.code for indicator in result.indicators
                ],
                "verification_case_id": (
                    str(verification_case_id)
                    if verification_case_id is not None
                    else None
                ),
                "requires_review": result.requires_review,
            },
        )

        # 4. Add both records to the transaction.
        db.add(assessment)
        db.add(audit)

        # 5. Commit or defer the transaction.
        if commit:
            db.commit()
            db.refresh(assessment)
        else:
            db.flush()

        # 6. Return the saved fraud assessment.
        return assessment

    except VerificationIntegrityError:
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()
        raise VerificationPersistenceError(
            "Failed to save risk assessment."
        ) from exc
