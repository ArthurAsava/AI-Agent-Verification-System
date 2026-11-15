
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db
from app.models.reviewer import Reviewer


def require_reviewer(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> uuid.UUID:
    reviewer = db.execute(
        select(Reviewer).where(
            Reviewer.user_id == user.id,
            Reviewer.is_active.is_(True),
        )
    ).scalar_one_or_none()

    if reviewer is None:
        raise HTTPException(
            status_code=403,
            detail="Active reviewer permission required.",
        )

    return user.id


def require_admin(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> uuid.UUID:
    """Require an active, server-managed verification administrator."""

    administrator = db.execute(
        select(Reviewer).where(
            Reviewer.user_id == user.id,
            Reviewer.is_active.is_(True),
            Reviewer.is_admin.is_(True),
        )
    ).scalar_one_or_none()

    if administrator is None:
        raise HTTPException(
            status_code=403,
            detail="Active administrator permission required.",
        )

    return user.id
