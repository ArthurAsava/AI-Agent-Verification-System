
import uuid
from dataclasses import dataclass

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings


bearer_scheme = HTTPBearer(auto_error=False)
MAX_BEARER_TOKEN_LENGTH = 8_192


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    email: str | None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reject obviously malformed bearer values locally. This avoids making an
    # external authentication request for input that cannot be a Supabase JWT;
    # JWT-shaped values are still verified by Supabase below.
    token = credentials.credentials
    if (
        len(token) > MAX_BEARER_TOKEN_LENGTH
        or len(token.split(".")) != 3
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()

    if not settings.SUPABASE_URL or not settings.SUPABASE_PUBLISHABLE_KEY:
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable",
        )

    url = (
        settings.SUPABASE_URL.rstrip("/")
        + "/auth/v1/user"
    )

    headers = {
        "apikey": settings.SUPABASE_PUBLISHABLE_KEY,
        "Authorization": (
            f"Bearer {token}"
        ),
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url,
                headers=headers,
            )
    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable",
        )

    if response.status_code in (401, 403):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable",
        )

    try:
        user_data = response.json()
        user_id = uuid.UUID(user_data["id"])
    except (ValueError, KeyError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication response",
        )

    if not user_data.get("email_confirmed_at"):
        raise HTTPException(
            status_code=403,
            detail="Email confirmation required",
        )

    return CurrentUser(
        id=user_id,
        email=user_data.get("email"),
    )
