
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.reviewer_auth import has_active_administrator_access
from app.schemas.agent import (
    AgentCreate,
    AgentResponse,
    AgentUpdate,
)
from app.services.agent_service import (
    create_agent,
    get_agent_by_user_id,
    update_agent,
)


router = APIRouter(
    prefix="/agents",
    tags=["Agents"],
)


@router.post(
    "/register",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_agent(
    payload: AgentCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = get_agent_by_user_id(db, user.id)

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Agent profile already exists",
        )

    try:
        return create_agent(
            db,
            user.id,
            payload,
            auto_approve=has_active_administrator_access(db, user.id),
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Agent profile could not be created",
        )


@router.get(
    "/me",
    response_model=AgentResponse,
)
def get_my_agent_profile(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agent = get_agent_by_user_id(db, user.id)

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail="Agent profile not found",
        )

    return agent


@router.patch(
    "/me",
    response_model=AgentResponse,
)
def update_my_agent_profile(
    payload: AgentUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agent = get_agent_by_user_id(db, user.id)

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail="Agent profile not found",
        )

    return update_agent(
        db,
        agent,
        payload,
        auto_approve=has_active_administrator_access(db, user.id),
    )
