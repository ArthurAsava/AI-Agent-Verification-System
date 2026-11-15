
from fastapi import APIRouter, Depends

from app.core.auth import (
    CurrentUser,
    get_current_user,
)


router = APIRouter(
    prefix="/kyc",
    tags=["KYC Preparation"],
)


@router.get("/requirements")
def get_kyc_requirements(
    user: CurrentUser = Depends(get_current_user),
):
    return {
        "identity_documents": {
            "selection": "one_of",
            "options": [
                {
                    "code": "national_id",
                    "name": "Kenyan National ID",
                    "description": (
                        "Prepare a valid Kenyan "
                        "National ID."
                    ),
                },
                {
                    "code": "passport",
                    "name": "Passport",
                    "description": (
                        "Prepare a valid passport."
                    ),
                },
            ],
        },
        "guidelines": [
            "Use your own valid identity document.",
            "Ensure the document is legible.",
            "Ensure the personal details match.",
            "Do not share identity documents by email.",
        ],
        "uploads_enabled": True,
        "verification_available": True,
    }
