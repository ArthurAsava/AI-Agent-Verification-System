
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Agent, AgentStatus, AuditLog
from app.models.verification_case import VerificationCase

from app.services.verification.decision_contracts import (
    CaseStatus,
    ReviewerAction,
)
from app.services.verification.state_machine import (
    validate_transition,
    InvalidVerificationTransition,
)


class ReviewerServiceError(RuntimeError):
    pass


class VerificationCaseNotFoundError(ReviewerServiceError):
    pass


class ReviewerAuthorizationError(ReviewerServiceError):
    pass


class VerificationDecisionConflictError(ReviewerServiceError):
    pass


class VerificationDecisionValidationError(ReviewerServiceError):
    pass


class VerificationDecisionPersistenceError(ReviewerServiceError):
    pass


@dataclass(frozen=True)
class ReviewerDecisionResult:
    case_id: uuid.UUID
    agent_id: uuid.UUID
    previous_status: str
    new_status: str
    reviewer_user_id: uuid.UUID
    decision_reason: str
    version: int
    reviewed_at: datetime


ACTION_TO_STATUS = {
    ReviewerAction.APPROVE: CaseStatus.APPROVED,
    ReviewerAction.REJECT: CaseStatus.REJECTED,
    ReviewerAction.REQUEST_RESUBMISSION: (
        CaseStatus.RESUBMISSION_REQUIRED
    ),
}

ACTION_TO_AGENT_STATUS = {
    ReviewerAction.APPROVE: AgentStatus.APPROVED,
    ReviewerAction.REJECT: AgentStatus.REJECTED,
    ReviewerAction.REQUEST_RESUBMISSION: AgentStatus.PENDING,
}


def record_verification_decision(
    *,
    db: Session,
    case_id: uuid.UUID,
    reviewer_user_id: uuid.UUID,
    action: ReviewerAction | str,
    reason: str,
    expected_version: int,
    reviewer_authorized: bool = False,
) -> ReviewerDecisionResult:

    if reviewer_authorized is not True:
        raise ReviewerAuthorizationError(
            "Reviewer permission is required."
        )

    if not isinstance(case_id, uuid.UUID):
        raise VerificationDecisionValidationError(
            "Invalid case ID."
        )

    if not isinstance(reviewer_user_id, uuid.UUID):
        raise VerificationDecisionValidationError(
            "Invalid reviewer ID."
        )

    if type(expected_version) is not int or expected_version < 0:
        raise VerificationDecisionValidationError(
            "Invalid case version."
        )

    try:
        normalized_action = ReviewerAction(action)
    except (ValueError, TypeError) as exc:
        raise VerificationDecisionValidationError(
            "Unsupported reviewer action."
        ) from exc

    if not isinstance(reason, str):
        raise VerificationDecisionValidationError(
            "Decision reason must be text."
        )

    normalized_reason = reason.strip()

    if not 10 <= len(normalized_reason) <= 1000:
        raise VerificationDecisionValidationError(
            "Decision reason must contain "
            "10 to 1000 characters."
        )

    try:
        case = db.execute(
            select(VerificationCase)
            .where(VerificationCase.id == case_id)
            .with_for_update()
        ).scalar_one_or_none()

        if case is None:
            raise VerificationCaseNotFoundError(
                "Verification case not found."
            )

        if case.version != expected_version:
            raise VerificationDecisionConflictError(
                "Case version has changed. Refresh and retry."
            )

        if case.status != CaseStatus.AWAITING_REVIEW.value:
            raise VerificationDecisionConflictError(
                "Case is not awaiting review."
            )

        agent = db.execute(
            select(Agent).where(
                Agent.id == case.agent_id
            )
        ).scalar_one_or_none()

        if agent is None:
            raise VerificationDecisionConflictError(
                "Agent associated with case not found."
            )

        if agent.user_id == reviewer_user_id:
            raise ReviewerAuthorizationError(
                "Reviewers cannot decide their own cases."
            )

        target_status = ACTION_TO_STATUS[normalized_action]

        try:
            validate_transition(
                CaseStatus(case.status),
                target_status,
            )
        except InvalidVerificationTransition as exc:
            raise VerificationDecisionConflictError(
                "Invalid verification state transition."
            ) from exc

        now = datetime.now(timezone.utc)
        previous_status = case.status

        case.status = target_status.value
        case.reviewer_user_id = reviewer_user_id
        case.decision_reason = normalized_reason
        case.reviewed_at = now
        case.updated_at = now
        case.version += 1

        # The agent's access state follows the human decision, never the
        # automated recommendation. Protected SalesMesh features can rely on
        # this server-controlled status.
        agent.status = ACTION_TO_AGENT_STATUS[normalized_action]

        audit = AuditLog(
            agent_id=case.agent_id,
            actor_user_id=reviewer_user_id,
            action=f"verification_{normalized_action.value}",
            details={
                "case_id": str(case.id),
                "previous_status": previous_status,
                "new_status": target_status.value,
                "version": case.version,
            },
        )

        db.add(audit)
        db.flush()

        result = ReviewerDecisionResult(
            case_id=case.id,
            agent_id=case.agent_id,
            previous_status=previous_status,
            new_status=target_status.value,
            reviewer_user_id=reviewer_user_id,
            decision_reason=normalized_reason,
            version=case.version,
            reviewed_at=now,
        )

        db.commit()
        return result

    except (
        VerificationCaseNotFoundError,
        ReviewerAuthorizationError,
        VerificationDecisionConflictError,
        VerificationDecisionValidationError,
    ):
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()
        raise VerificationDecisionPersistenceError(
            "Failed to record verification decision."
        ) from exc
