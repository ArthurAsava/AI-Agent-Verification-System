
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Agent
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
    )

    db.add(agent)
    db.commit()
    db.refresh(agent)

    return agent


def update_agent(
    db: Session,
    agent: Agent,
    payload: AgentUpdate,
) -> Agent:
    changes = payload.model_dump(exclude_unset=True)

    for field, value in changes.items():
        setattr(agent, field, value)

    db.commit()
    db.refresh(agent)

    return agent
