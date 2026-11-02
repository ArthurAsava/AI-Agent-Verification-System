
from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.get("/me")
def get_authenticated_user(
    user: CurrentUser = Depends(get_current_user),
):
    return {
        "id": str(user.id),
        "email": user.email,
    }
