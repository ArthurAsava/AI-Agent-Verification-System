"""Secure, self-service deletion of a regular user's Verity account."""

from __future__ import annotations

import uuid
import base64
import json
from dataclasses import dataclass

import httpx
from sqlalchemy import delete, or_, select, text
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.config import get_settings
from app.models.entities import Agent, AuditLog, KYCDocument
from app.models.reviewer import Reviewer
from app.models.verification_case import VerificationCase
from app.services.storage_service import (
    StorageOperationError,
    SupabaseStorageService,
)


class AccountDeletionError(RuntimeError):
    """The account could not be deleted safely."""


class AccountDeletionForbiddenError(AccountDeletionError):
    """The account has a staff/reviewer role and cannot self-delete."""


class AccountDeletionPasswordError(AccountDeletionError):
    """The supplied password did not authenticate the current user."""


class AccountDeletionServiceUnavailableError(AccountDeletionError):
    """Supabase Auth could not confirm the password."""


class AccountDeletionStorageError(AccountDeletionError):
    """A private document could not be removed from Storage."""


class AccountDeletionPersistenceError(AccountDeletionError):
    """Database changes for the account deletion could not be committed."""


@dataclass(frozen=True)
class StoredDocument:
    bucket: str
    path: str


@dataclass(frozen=True)
class AccountDeletionPlan:
    agent_id: uuid.UUID | None
    documents: tuple[StoredDocument, ...]


def is_self_service_deletion_eligible(
    db: Session,
    user_id: uuid.UUID,
) -> bool:
    """Reviewer/staff accounts must be removed through an administrator."""

    reviewer = db.scalar(
        select(Reviewer.user_id).where(Reviewer.user_id == user_id)
    )
    return reviewer is None


async def verify_account_password(
    user: CurrentUser,
    password: str,
) -> uuid.UUID:
    """Authenticate the password and bind the result to the current account."""

    if not user.email:
        raise AccountDeletionPasswordError("Password is incorrect.")

    settings = get_settings()
    if not settings.SUPABASE_URL or not settings.SUPABASE_PUBLISHABLE_KEY:
        raise AccountDeletionServiceUnavailableError(
            "Authentication service is unavailable."
        )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                (
                    f"{settings.SUPABASE_URL.rstrip('/')}"
                    "/auth/v1/token?grant_type=password"
                ),
                headers={
                    "apikey": settings.SUPABASE_PUBLISHABLE_KEY,
                    "Content-Type": "application/json",
                },
                json={"email": user.email, "password": password},
            )
    except httpx.RequestError as exc:
        raise AccountDeletionServiceUnavailableError(
            "Authentication service is unavailable."
        ) from exc

    if response.status_code in (400, 401, 403, 422):
        raise AccountDeletionPasswordError("Password is incorrect.")

    if response.status_code != 200:
        raise AccountDeletionServiceUnavailableError(
            "Authentication service is unavailable."
        )

    try:
        response_data = response.json()
        authenticated_user_id = uuid.UUID(response_data["user"]["id"])
        access_token = response_data["access_token"]
        session_id = _session_id_from_auth_response(access_token)
    except (KeyError, TypeError, ValueError):
        raise AccountDeletionServiceUnavailableError(
            "Authentication service is unavailable."
        )

    if authenticated_user_id != user.id:
        raise AccountDeletionPasswordError("Password is incorrect.")

    if session_id is None:
        raise AccountDeletionServiceUnavailableError(
            "Authentication service is unavailable."
        )

    return session_id


def _session_id_from_auth_response(access_token: object) -> uuid.UUID | None:
    """Extract only the session id created by a successful Auth response."""

    if not isinstance(access_token, str):
        return None

    try:
        encoded_payload = access_token.split(".")[1]
        padded_payload = encoded_payload + "=" * (
            -len(encoded_payload) % 4
        )
        payload = json.loads(
            base64.urlsafe_b64decode(padded_payload).decode("utf-8")
        )
        return uuid.UUID(payload["session_id"])
    except (
        IndexError,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return None


def _revoke_confirmation_session(
    db: Session,
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    """Best-effort cleanup for the password grant after a failed deletion."""

    try:
        db.execute(
            text(
                "DELETE FROM auth.sessions "
                "WHERE id = :session_id AND user_id = :user_id"
            ),
            {"session_id": session_id, "user_id": user_id},
        )
        db.commit()
    except Exception:
        # The deletion request has already failed safely. Do not hide its
        # accurate error behind a secondary cleanup failure.
        db.rollback()


def _build_deletion_plan(
    db: Session,
    user_id: uuid.UUID,
) -> AccountDeletionPlan:
    """Lock the user's profile and collect only its server-recorded objects."""

    if not is_self_service_deletion_eligible(db, user_id):
        raise AccountDeletionForbiddenError(
            "Reviewer accounts cannot be deleted from this page."
        )

    agent = db.scalar(
        select(Agent)
        .where(Agent.user_id == user_id)
        .with_for_update()
    )
    if agent is None:
        return AccountDeletionPlan(agent_id=None, documents=())

    documents = db.scalars(
        select(KYCDocument).where(KYCDocument.agent_id == agent.id)
    ).all()
    return AccountDeletionPlan(
        agent_id=agent.id,
        documents=tuple(
            StoredDocument(
                bucket=document.storage_bucket,
                path=document.storage_path,
            )
            for document in documents
        ),
    )


async def delete_own_account(
    *,
    db: Session,
    storage: SupabaseStorageService,
    user: CurrentUser,
    password: str,
) -> None:
    """Remove the current regular user's private files, data and Auth user.

    Password confirmation occurs before obtaining the deletion plan. Storage
    is removed first so database records never claim a deleted account while
    retaining retrievable identity documents. The database commit then removes
    the public records, revokes every Auth session and deletes the Auth user.
    """

    confirmation_session_id = await verify_account_password(user, password)

    try:
        plan = _build_deletion_plan(db, user.id)

        for document in plan.documents:
            await storage.delete(document.path, bucket=document.bucket)
    except AccountDeletionError:
        db.rollback()
        _revoke_confirmation_session(
            db,
            user_id=user.id,
            session_id=confirmation_session_id,
        )
        raise
    except (StorageOperationError, ValueError) as exc:
        db.rollback()
        _revoke_confirmation_session(
            db,
            user_id=user.id,
            session_id=confirmation_session_id,
        )
        raise AccountDeletionStorageError(
            "Private documents could not be deleted."
        ) from exc

    try:
        # Check a second time in the same transaction before destructive work.
        # This also prevents a reviewer role from being added concurrently.
        if not is_self_service_deletion_eligible(db, user.id):
            raise AccountDeletionForbiddenError(
                "Reviewer accounts cannot be deleted from this page."
            )

        if plan.agent_id is not None:
            # Verification cases reference the document and profile without
            # cascading, so remove them before deleting the profile itself.
            db.execute(
                delete(VerificationCase).where(
                    VerificationCase.agent_id == plan.agent_id
                )
            )
            db.execute(
                delete(AuditLog).where(
                    or_(
                        AuditLog.agent_id == plan.agent_id,
                        AuditLog.actor_user_id == user.id,
                    )
                )
            )
            # KYC documents, onboarding, checks, and assessments use database
            # cascades from agents. Their Storage objects were removed above.
            db.execute(delete(Agent).where(Agent.id == plan.agent_id))
        else:
            db.execute(
                delete(AuditLog).where(AuditLog.actor_user_id == user.id)
            )

        # Deleting auth.users does not invalidate issued JWTs by itself, so
        # remove every session before deleting the authenticated identity.
        db.execute(
            text("DELETE FROM auth.sessions WHERE user_id = :user_id"),
            {"user_id": user.id},
        )
        deleted_user = db.execute(
            text(
                "DELETE FROM auth.users "
                "WHERE id = :user_id "
                "RETURNING id"
            ),
            {"user_id": user.id},
        ).scalar_one_or_none()
        if deleted_user is None:
            raise AccountDeletionPersistenceError(
                "Account could not be deleted."
            )

        db.commit()
    except AccountDeletionForbiddenError:
        db.rollback()
        _revoke_confirmation_session(
            db,
            user_id=user.id,
            session_id=confirmation_session_id,
        )
        raise
    except AccountDeletionPersistenceError:
        db.rollback()
        _revoke_confirmation_session(
            db,
            user_id=user.id,
            session_id=confirmation_session_id,
        )
        raise
    except Exception as exc:
        db.rollback()
        _revoke_confirmation_session(
            db,
            user_id=user.id,
            session_id=confirmation_session_id,
        )
        raise AccountDeletionPersistenceError(
            "Account could not be deleted."
        ) from exc
