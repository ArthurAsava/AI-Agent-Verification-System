
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Agent, AgentStatus, AuditLog
from app.schemas.agent import AgentCreate, AgentUpdate


def get_agent_by_user_id(
    db: Session,
    user_id: uuid.UUID,
) -> Agent | None:
    return db.scalar(
        select(Agent).where(Agent.user_id == user_id)
    )


def create_agent(
    db: Session,
    user_id: uuid.UUID,
    payload: AgentCreate,
    *,
    auto_approve: bool = False,
) -> Agent:
    agent = Agent(
        user_id=user_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone_number=payload.phone_number,
        date_of_birth=payload.date_of_birth,
        primary_residence=payload.primary_residence,
        nationality=payload.nationality,
        avatar_variant=payload.avatar_variant,
        status=(
            AgentStatus.APPROVED
            if auto_approve
            else AgentStatus.PENDING
        ),
    )

    db.add(agent)
    if auto_approve:
        db.flush()
        db.add(
            AuditLog(
                agent_id=agent.id,
                actor_user_id=user_id,
                action="administrator_profile_auto_approved",
                details={"reason": "active_administrator_profile"},
            )
        )
    db.commit()
    db.refresh(agent)

    return agent


def update_agent(
    db: Session,
    agent: Agent,
    payload: AgentUpdate,
    *,
    auto_approve: bool = False,
) -> Agent:
    changes = payload.model_dump(exclude_unset=True)

    for field, value in changes.items():
        setattr(agent, field, value)

    if auto_approve and agent.status != AgentStatus.APPROVED:
        previous_status = agent.status
        agent.status = AgentStatus.APPROVED
        db.add(
            AuditLog(
                agent_id=agent.id,
                actor_user_id=agent.user_id,
                action="administrator_profile_auto_approved",
                details={
                    "reason": "active_administrator_profile",
                    "previous_status": previous_status.value,
                },
            )
        )

    db.commit()
    db.refresh(agent)

    return agent
