
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from app.core.auth import (
    CurrentUser,
    get_current_user,
)
from app.core.database import get_db
from app.schemas.onboarding import (
    OnboardingResponse,
    OnboardingUpdate,
)
from app.services.agent_service import (
    get_agent_by_user_id,
)
from app.services.onboarding_service import (
    calculate_progress,
    get_onboarding,
    save_onboarding,
)


router = APIRouter(
    prefix="/onboarding",
    tags=["Onboarding"],
)


def build_response(agent, onboarding):
    values = {
        "first_name": agent.first_name,
        "last_name": agent.last_name,
        "phone_number": agent.phone_number,
        "county": (
            onboarding.county
            if onboarding else None
        ),
        "city": (
            onboarding.city
            if onboarding else None
        ),
    }

    status_value = agent.status
    if hasattr(status_value, "value"):
        status_value = status_value.value

    return OnboardingResponse(
        agent_id=str(agent.id),
        first_name=agent.first_name,
        last_name=agent.last_name,
        phone_number=agent.phone_number,
        county=values["county"],
        city=values["city"],
        business_name=(
            onboarding.business_name
            if onboarding else None
        ),
        experience_level=(
            onboarding.experience_level
            if onboarding else None
        ),
        preferred_sales_category=(
            onboarding.preferred_sales_category
            if onboarding else None
        ),
        agent_status=status_value,
        progress=calculate_progress(values),
    )


@router.get(
    "/me",
    response_model=OnboardingResponse,
)
def get_my_onboarding(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agent = get_agent_by_user_id(db, user.id)

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail="Complete agent registration first",
        )

    onboarding = get_onboarding(db, agent.id)

    return build_response(agent, onboarding)


@router.patch(
    "/me",
    response_model=OnboardingResponse,
)
def update_my_onboarding(
    payload: OnboardingUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agent = get_agent_by_user_id(db, user.id)

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail="Complete agent registration first",
        )

    onboarding = save_onboarding(
        db,
        agent.id,
        payload,
    )

    return build_response(agent, onboarding)

