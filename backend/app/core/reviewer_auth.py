
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db
from app.models.reviewer import Reviewer


def has_active_administrator_access(
    db: Session,
    user_id: uuid.UUID,
) -> bool:
    """Return server-controlled administrator access for one user."""

    administrator = db.execute(
        select(Reviewer.user_id).where(
            Reviewer.user_id == user_id,
            Reviewer.is_active.is_(True),
            Reviewer.is_admin.is_(True),
        )
    ).scalar_one_or_none()
    return administrator is not None


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

    if not has_active_administrator_access(db, user.id):
        raise HTTPException(
            status_code=403,
            detail="Active administrator permission required.",
        )

    return user.id
