"""Server-controlled administration for the verification workflow."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import Agent, AgentStatus, AuditLog
from app.models.reviewer import Reviewer
from app.models.verification_case import VerificationCase


class VerificationAdministrationError(RuntimeError):
    pass


class ReviewerAccountNotFoundError(VerificationAdministrationError):
    pass


class ReviewerAccessValidationError(VerificationAdministrationError):
    pass


class AgentCategoryValidationError(VerificationAdministrationError):
    pass


AGENT_CATEGORIES: dict[str, tuple[AgentStatus, ...]] = {
    # Include pending profiles so every regular agent who has begun onboarding
    # remains visible to administrators until a staff decision is recorded.
    "waiting": (AgentStatus.PENDING, AgentStatus.UNDER_REVIEW),
    "approved": (AgentStatus.APPROVED,),
    "rejected": (AgentStatus.REJECTED,),
}


@dataclass(frozen=True)
class AdminDashboardSummary:
    awaiting_review_cases: int
    elevated_risk_cases: int
    new_cases_last_24_hours: int
    agents_under_review: int
    active_reviewers: int
    waiting_agents: int
    approved_agents: int
    rejected_agents: int


@dataclass(frozen=True)
class ReviewerAccessRecord:
    user_id: uuid.UUID
    is_active: bool
    is_admin: bool
    created_at: datetime


@dataclass(frozen=True)
class AdminAgentRecord:
    id: uuid.UUID
    user_id: uuid.UUID
    first_name: str
    last_name: str
    phone_number: str | None
    date_of_birth: date | None
    primary_residence: str | None
    nationality: str | None
    avatar_variant: str | None
    status: AgentStatus
    created_at: datetime
    updated_at: datetime


def _count(db: Session, statement) -> int:
    return int(db.execute(statement).scalar_one())


def get_admin_dashboard_summary(
    db: Session,
) -> AdminDashboardSummary:
    """Return aggregate workflow health without identity or biometric data."""

    window_start = datetime.now(timezone.utc) - timedelta(hours=24)
    return AdminDashboardSummary(
        awaiting_review_cases=_count(
            db,
            select(func.count(VerificationCase.id)).where(
                VerificationCase.status == "awaiting_review"
            ),
        ),
        elevated_risk_cases=_count(
            db,
            select(func.count(VerificationCase.id)).where(
                VerificationCase.status == "awaiting_review",
                VerificationCase.risk_level.in_(("high", "critical")),
            ),
        ),
        new_cases_last_24_hours=_count(
            db,
            select(func.count(VerificationCase.id)).where(
                VerificationCase.created_at >= window_start
            ),
        ),
        agents_under_review=_count(
            db,
            select(func.count(Agent.id)).where(
                Agent.status == AgentStatus.UNDER_REVIEW
            ),
        ),
        active_reviewers=_count(
            db,
            select(func.count(Reviewer.user_id)).where(
                Reviewer.is_active.is_(True)
            ),
        ),
        waiting_agents=_count(
            db,
            select(func.count(Agent.id)).where(
                Agent.status.in_(AGENT_CATEGORIES["waiting"])
            ),
        ),
        approved_agents=_count(
            db,
            select(func.count(Agent.id)).where(
                Agent.status == AgentStatus.APPROVED
            ),
        ),
        rejected_agents=_count(
            db,
            select(func.count(Agent.id)).where(
                Agent.status == AgentStatus.REJECTED
            ),
        ),
    )


def list_agents_by_category(
    db: Session,
    category: str,
) -> list[AdminAgentRecord]:
    """List agent profile data for one administrator-only status category."""

    statuses = AGENT_CATEGORIES.get(category)
    if statuses is None:
        raise AgentCategoryValidationError("Unknown agent category.")

    agents = db.execute(
        select(Agent)
        .where(Agent.status.in_(statuses))
        .order_by(Agent.updated_at.desc(), Agent.created_at.desc())
    ).scalars().all()
    return [
        AdminAgentRecord(
            id=agent.id,
            user_id=agent.user_id,
            first_name=agent.first_name,
            last_name=agent.last_name,
            phone_number=agent.phone_number,
            date_of_birth=agent.date_of_birth,
            primary_residence=agent.primary_residence,
            nationality=agent.nationality,
            avatar_variant=(
                agent.avatar_variant.value
                if agent.avatar_variant is not None
                else None
            ),
            status=agent.status,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )
        for agent in agents
    ]


def list_reviewer_access(
    db: Session,
) -> list[ReviewerAccessRecord]:
    reviewers = db.execute(
        select(Reviewer).order_by(Reviewer.created_at.asc())
    ).scalars().all()
    return [
        ReviewerAccessRecord(
            user_id=reviewer.user_id,
            is_active=reviewer.is_active,
            is_admin=reviewer.is_admin,
            created_at=reviewer.created_at,
        )
        for reviewer in reviewers
    ]


def update_reviewer_access(
    *,
    db: Session,
    administrator_user_id: uuid.UUID,
    target_user_id: uuid.UUID,
    is_active: bool,
    is_admin: bool,
) -> ReviewerAccessRecord:
    """Create or update staff access while preventing an admin lockout."""

    if type(is_active) is not bool or type(is_admin) is not bool:
        raise ReviewerAccessValidationError(
            "Reviewer access values must be boolean."
        )
    if target_user_id == administrator_user_id and (
        not is_active or not is_admin
    ):
        raise ReviewerAccessValidationError(
            "Administrators cannot remove their own active administrator access."
        )

    try:
        # SalesMesh reviewer accounts must belong to a registered agent. This
        # verifies the target before a foreign-key constraint could disclose
        # database internals to an API caller.
        target_agent = db.execute(
            select(Agent).where(Agent.user_id == target_user_id)
        ).scalar_one_or_none()
        if target_agent is None:
            raise ReviewerAccountNotFoundError(
                "Target user does not have a SalesMesh agent profile."
            )

        reviewer = db.execute(
            select(Reviewer)
            .where(Reviewer.user_id == target_user_id)
            .with_for_update()
        ).scalar_one_or_none()

        if reviewer is not None and reviewer.is_active and reviewer.is_admin:
            active_administrators = db.execute(
                select(Reviewer)
                .where(
                    Reviewer.is_active.is_(True),
                    Reviewer.is_admin.is_(True),
                )
                .with_for_update()
            ).scalars().all()
            if len(active_administrators) <= 1 and (
                not is_active or not is_admin
            ):
                raise ReviewerAccessValidationError(
                    "At least one active administrator is required."
                )

        if reviewer is None:
            reviewer = Reviewer(
                user_id=target_user_id,
                is_active=is_active,
                is_admin=is_admin,
            )
            db.add(reviewer)
        else:
            reviewer.is_active = is_active
            reviewer.is_admin = is_admin

        db.add(
            AuditLog(
                agent_id=target_agent.id,
                actor_user_id=administrator_user_id,
                action="verification_reviewer_access_updated",
                details={
                    "target_user_id": str(target_user_id),
                    "is_active": is_active,
                    "is_admin": is_admin,
                },
            )
        )
        db.flush()
        result = ReviewerAccessRecord(
            user_id=reviewer.user_id,
            is_active=reviewer.is_active,
            is_admin=reviewer.is_admin,
            created_at=reviewer.created_at,
        )
        db.commit()
        return result
    except (
        ReviewerAccountNotFoundError,
        ReviewerAccessValidationError,
    ):
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise VerificationAdministrationError(
            "Could not update reviewer access."
        ) from exc
