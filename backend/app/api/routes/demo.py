
from fastapi import APIRouter

from app.schemas.common import DemoRequest, DemoResponse
from app.core.exceptions import AppException

router = APIRouter(
    prefix="/demo",
    tags=["Development"],
)


@router.post(
    "/validate",
    response_model=DemoResponse,
)
def validate_demo(payload: DemoRequest):
    return DemoResponse(
        message="Validation successful",
        name=payload.name,
        age=payload.age,
    )

@router.get("/error")
def demonstrate_error():
    raise AppException(
        message="Demonstration error",
        status_code=400,
        error_code="DEMO_ERROR",
    )