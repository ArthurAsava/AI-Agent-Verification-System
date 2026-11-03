
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.onboarding import AgentOnboarding
from app.schemas.onboarding import (
    OnboardingProgress,
    OnboardingUpdate,
)


REQUIRED_FIELDS = (
    "first_name",
    "last_name",
    "phone_number",
    "county",
    "city",
)


def calculate_progress(
    values: dict,
) -> OnboardingProgress:
    missing = [
        field
        for field in REQUIRED_FIELDS
        if not isinstance(values.get(field), str)
        or not values[field].strip()
    ]

    total = len(REQUIRED_FIELDS)
    completed = total - len(missing)

    return OnboardingProgress(
        completed_fields=completed,
        total_fields=total,
        percentage=round(completed / total * 100),
        missing_fields=missing,
        profile_complete=(completed == total),
    )


def get_onboarding(
    db: Session,
    agent_id,
) -> AgentOnboarding | None:
    return db.scalar(
        select(AgentOnboarding).where(
            AgentOnboarding.agent_id == agent_id
        )
    )


def save_onboarding(
    db: Session,
    agent_id,
    payload: OnboardingUpdate,
) -> AgentOnboarding:
    onboarding = get_onboarding(db, agent_id)

    if onboarding is None:
        onboarding = AgentOnboarding(
            agent_id=agent_id
        )
        db.add(onboarding)

    changes = payload.model_dump(
        exclude_unset=True
    )

    for field, value in changes.items():
        setattr(onboarding, field, value)

    db.commit()
    db.refresh(onboarding)

    return onboarding
