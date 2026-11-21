
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.security import SlidingWindowRateLimiter
from app.schemas.account_deletion import (
    AccountDeletionEligibilityResponse,
    AccountDeletionRequest,
    AccountDeletionResponse,
)
from app.schemas.session import AccountSessionResponse
from app.services.account_deletion_service import (
    AccountDeletionForbiddenError,
    AccountDeletionPasswordError,
    AccountDeletionPersistenceError,
    AccountDeletionServiceUnavailableError,
    AccountDeletionStorageError,
    delete_own_account,
    is_self_service_deletion_eligible,
)
from app.services.storage_service import (
    StorageConfigurationError,
    SupabaseStorageService,
    get_storage_service,
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

# Password confirmation is intentionally a much tighter limit than ordinary
# API traffic. It limits online password guessing even for a valid session.
account_deletion_password_limiter = SlidingWindowRateLimiter(
    limit=5,
    window_seconds=15 * 60,
    max_clients=10_000,
)


def get_account_deletion_storage() -> SupabaseStorageService:
    """Expose an intentional 503 instead of a configuration traceback."""

    try:
        return get_storage_service()
    except StorageConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Private document storage is unavailable.",
        ) from exc


@router.get("/me")
def get_authenticated_user(
    user: CurrentUser = Depends(get_current_user),
):
    return {
        "id": str(user.id),
        "email": user.email,
    }


@router.get(
    "/sessions",
    response_model=list[AccountSessionResponse],
)
def get_authenticated_user_sessions(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the authenticated user's safe Auth session summaries only."""

    rows = db.execute(
        text(
            """
            SELECT
                id,
                created_at,
                COALESCE(
                    refreshed_at AT TIME ZONE 'UTC',
                    updated_at,
                    created_at
                ) AS last_active_at,
                not_after AS expires_at,
                user_agent
            FROM auth.sessions
            WHERE user_id = :user_id
            ORDER BY COALESCE(
                refreshed_at AT TIME ZONE 'UTC',
                updated_at,
                created_at
            ) DESC NULLS LAST
            """
        ),
        {"user_id": user.id},
    ).mappings()

    return [
        AccountSessionResponse(
            id=row["id"],
            created_at=row["created_at"],
            last_active_at=row["last_active_at"],
            expires_at=row["expires_at"],
            # Avoid presenting unbounded, control-character-containing values
            # from a user agent header in the account security page.
            user_agent=(
                " ".join(str(row["user_agent"]).split())[:180]
                if row["user_agent"]
                else None
            ),
            is_current=row["id"] == user.session_id,
        )
        for row in rows
    ]


@router.get(
    "/account-deletion-eligibility",
    response_model=AccountDeletionEligibilityResponse,
)
def get_account_deletion_eligibility(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tell the UI whether a regular user may use self-service deletion."""

    return AccountDeletionEligibilityResponse(
        eligible=is_self_service_deletion_eligible(db, user.id)
    )


@router.post(
    "/delete-account",
    response_model=AccountDeletionResponse,
)
async def delete_authenticated_user_account(
    payload: AccountDeletionRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: SupabaseStorageService = Depends(
        get_account_deletion_storage
    ),
):
    """Permanently delete only the authenticated regular user's account."""

    allowed, retry_after = account_deletion_password_limiter.allow(
        f"account-deletion:{user.id}"
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many password confirmation attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    try:
        await delete_own_account(
            db=db,
            storage=storage,
            user=user,
            password=payload.password.get_secret_value(),
        )
    except AccountDeletionPasswordError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password is incorrect.",
        ) from exc
    except AccountDeletionForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account cannot be deleted from this page.",
        ) from exc
    except (
        AccountDeletionServiceUnavailableError,
        AccountDeletionStorageError,
        AccountDeletionPersistenceError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Account deletion could not be completed. Please try again.",
        ) from exc

    return AccountDeletionResponse()
