from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.entities import (
    Agent,
    AuditLog,
    CheckStatus,
    KYCDocument,
    VerificationCheck,
)
from app.services.storage_service import (
    StorageOperationError,
    SupabaseStorageService,
)
from app.services.kyc_upload_service import (
    BIOMETRIC_DIDIT_CHECK_TYPE,
    BIOMETRIC_SELFIE_CHECK_TYPE,
    BIOMETRIC_SELFIE_DOCUMENT_TYPE,
)


COMPARABLE_IDENTITY_DOCUMENT_TYPES = frozenset({
    "national_id_front",
    "passport",
})


class BiometricReviewError(RuntimeError):
    """Base error for the manual biometric evidence workflow."""


class BiometricReviewNotFoundError(BiometricReviewError):
    pass


class BiometricReviewConflictError(BiometricReviewError):
    pass


class BiometricReviewValidationError(BiometricReviewError):
    pass


class BiometricReviewRetrievalError(BiometricReviewError):
    pass


class BiometricReviewPersistenceError(BiometricReviewError):
    pass


@dataclass(frozen=True)
class ReviewDocument:
    document_id: uuid.UUID
    document_type: str
    original_filename: str | None
    mime_type: str | None
    file_size_bytes: int | None
    status: str


@dataclass(frozen=True)
class BiometricReviewItem:
    check_id: uuid.UUID
    agent_id: uuid.UUID
    created_at: datetime | None
    selfie: ReviewDocument | None
    identity_documents: list[ReviewDocument]
    provider_summary: "ProviderSummary | None"


@dataclass(frozen=True)
class ProviderSummary:
    provider: str
    mode: str
    submission_status: str
    result_code: str | None
    result_text: str | None
    is_final: bool | None
    actions: dict[str, str]


@dataclass(frozen=True)
class BiometricReviewDecisionResult:
    check_id: uuid.UUID
    previous_status: str
    new_status: str
    reviewed_at: datetime


@dataclass(frozen=True)
class _PrivateReviewDocument:
    document_id: uuid.UUID
    agent_id: uuid.UUID
    document_type: str
    original_filename: str | None
    mime_type: str | None
    storage_path: str
    storage_bucket: str


def _status_value(status: object) -> str:
    return status.value if hasattr(status, "value") else str(status)


def _to_summary(document: KYCDocument) -> ReviewDocument:
    return ReviewDocument(
        document_id=document.id,
        document_type=document.document_type,
        original_filename=document.original_filename,
        mime_type=document.mime_type,
        file_size_bytes=document.file_size_bytes,
        status=_status_value(document.status),
    )


def _selfie_document_id(check: VerificationCheck) -> uuid.UUID | None:
    value = (check.result_data or {}).get("selfie_document_id")
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _provider_summary(check: VerificationCheck) -> ProviderSummary | None:
    didit_data = (check.result_data or {}).get("didit")
    if not isinstance(didit_data, dict):
        return None

    result = didit_data.get("result")
    result = result if isinstance(result, dict) else {}
    raw_actions = result.get("actions")
    raw_actions = raw_actions if isinstance(raw_actions, dict) else {}
    actions = {
        str(name)[:100]: str(value)[:100]
        for name, value in raw_actions.items()
        if isinstance(name, str) and isinstance(value, str)
    }
    return ProviderSummary(
        provider="didit",
        mode=str(didit_data.get("mode", "unknown"))[:100],
        submission_status=str(
            didit_data.get("submission_status", "unknown")
        )[:100],
        result_code=(
            str(result["result_code"])[:20]
            if result.get("result_code") is not None
            else None
        ),
        result_text=(
            str(result["result_text"])[:500]
            if result.get("result_text") is not None
            else None
        ),
        is_final=(
            result["is_final"]
            if isinstance(result.get("is_final"), bool)
            else None
        ),
        actions=actions,
    )


def list_pending_biometric_reviews(
    db: Session,
) -> list[BiometricReviewItem]:
    """Return only intact pending work items and safe file metadata."""

    checks = db.execute(
        select(VerificationCheck)
        .where(
            VerificationCheck.check_type.in_(
                (BIOMETRIC_SELFIE_CHECK_TYPE, BIOMETRIC_DIDIT_CHECK_TYPE)
            ),
            VerificationCheck.status == CheckStatus.NEEDS_REVIEW,
        )
        .order_by(VerificationCheck.created_at.asc())
    ).scalars().all()

    items: list[BiometricReviewItem] = []
    for check in checks:
        selfie_id = _selfie_document_id(check)
        selfie = None
        if selfie_id is not None:
            selfie = db.execute(
                select(KYCDocument).where(
                    KYCDocument.id == selfie_id,
                    KYCDocument.agent_id == check.agent_id,
                    KYCDocument.document_type == BIOMETRIC_SELFIE_DOCUMENT_TYPE,
                )
            ).scalar_one_or_none()
        if (
            check.check_type == BIOMETRIC_SELFIE_CHECK_TYPE
            and selfie is None
        ):
            continue

        identity_documents = db.execute(
            select(KYCDocument)
            .where(
                KYCDocument.agent_id == check.agent_id,
                KYCDocument.document_type.in_(
                    COMPARABLE_IDENTITY_DOCUMENT_TYPES
                ),
            )
            .order_by(KYCDocument.uploaded_at.desc())
        ).scalars().all()

        items.append(
            BiometricReviewItem(
                check_id=check.id,
                agent_id=check.agent_id,
                created_at=check.created_at,
                selfie=_to_summary(selfie) if selfie is not None else None,
                identity_documents=[
                    _to_summary(document)
                    for document in identity_documents
                ],
                provider_summary=_provider_summary(check),
            )
        )

    return items


def record_biometric_review_decision(
    *,
    db: Session,
    check_id: uuid.UUID,
    reviewer_user_id: uuid.UUID,
    action: str,
    reason: str,
) -> BiometricReviewDecisionResult:
    """Record a human biometric-evidence decision without changing Agent.status."""

    if not isinstance(check_id, uuid.UUID):
        raise BiometricReviewValidationError("Invalid biometric check ID.")
    if not isinstance(reviewer_user_id, uuid.UUID):
        raise BiometricReviewValidationError("Invalid reviewer ID.")
    if action not in {
        "confirm_match",
        "request_resubmission",
        "reject_capture",
    }:
        raise BiometricReviewValidationError(
            "Unsupported biometric review action."
        )
    if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 1000:
        raise BiometricReviewValidationError(
            "Decision reason must contain 10 to 1000 characters."
        )

    try:
        check = db.execute(
            select(VerificationCheck)
            .where(
                VerificationCheck.id == check_id,
                VerificationCheck.check_type.in_(
                    (BIOMETRIC_SELFIE_CHECK_TYPE, BIOMETRIC_DIDIT_CHECK_TYPE)
                ),
            )
            .with_for_update()
        ).scalar_one_or_none()
        if check is None:
            raise BiometricReviewNotFoundError(
                "Biometric review item not found."
            )
        if check.status != CheckStatus.NEEDS_REVIEW:
            raise BiometricReviewConflictError(
                "Biometric review item is no longer awaiting review."
            )

        agent = db.execute(
            select(Agent).where(Agent.id == check.agent_id)
        ).scalar_one_or_none()
        if agent is None:
            raise BiometricReviewConflictError(
                "Agent associated with biometric review was not found."
            )
        if agent.user_id == reviewer_user_id:
            raise BiometricReviewValidationError(
                "Reviewers cannot decide their own biometric evidence."
            )

        now = datetime.now(timezone.utc)
        previous_status = _status_value(check.status)
        new_status = (
            CheckStatus.PASSED
            if action == "confirm_match"
            else CheckStatus.FAILED
        )

        result_data = dict(check.result_data or {})
        result_data.update({
            "manual_review_status": action,
            "reviewed_at": now.isoformat(),
        })
        check.status = new_status
        check.result_data = result_data

        db.add(
            AuditLog(
                agent_id=check.agent_id,
                actor_user_id=reviewer_user_id,
                action=f"biometric_review_{action}",
                details={
                    "check_id": str(check.id),
                    "previous_status": previous_status,
                    "new_status": new_status.value,
                    "reason": reason.strip(),
                },
            )
        )
        db.flush()
        db.commit()

        return BiometricReviewDecisionResult(
            check_id=check.id,
            previous_status=previous_status,
            new_status=new_status.value,
            reviewed_at=now,
        )
    except (
        BiometricReviewNotFoundError,
        BiometricReviewConflictError,
        BiometricReviewValidationError,
    ):
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise BiometricReviewPersistenceError(
            "Failed to record biometric review decision."
        ) from exc


def _load_biometric_review_document_sync(
    reviewer_user_id: uuid.UUID,
    check_id: uuid.UUID,
    document_id: uuid.UUID,
) -> _PrivateReviewDocument:
    with SessionLocal() as db:
        check = db.execute(
            select(VerificationCheck).where(
                VerificationCheck.id == check_id,
                VerificationCheck.check_type.in_(
                    (BIOMETRIC_SELFIE_CHECK_TYPE, BIOMETRIC_DIDIT_CHECK_TYPE)
                ),
                VerificationCheck.status == CheckStatus.NEEDS_REVIEW,
            )
        ).scalar_one_or_none()
        if check is None:
            raise BiometricReviewNotFoundError(
                "Biometric review item not found."
            )

        selfie_id = _selfie_document_id(check)

        document = db.execute(
            select(KYCDocument).where(
                KYCDocument.id == document_id,
                KYCDocument.agent_id == check.agent_id,
            )
        ).scalar_one_or_none()
        if document is None:
            raise BiometricReviewNotFoundError("Review document not found.")

        is_selfie = (
            selfie_id is not None
            and document.id == selfie_id
            and document.document_type == BIOMETRIC_SELFIE_DOCUMENT_TYPE
        )
        is_identity_document = (
            document.document_type in COMPARABLE_IDENTITY_DOCUMENT_TYPES
        )
        if not is_selfie and not is_identity_document:
            raise BiometricReviewNotFoundError("Review document not found.")

        return _PrivateReviewDocument(
            document_id=document.id,
            agent_id=document.agent_id,
            document_type=document.document_type,
            original_filename=document.original_filename,
            mime_type=document.mime_type,
            storage_path=document.storage_path,
            storage_bucket=document.storage_bucket,
        )


def _record_biometric_document_view_sync(
    reviewer_user_id: uuid.UUID,
    check_id: uuid.UUID,
    document: _PrivateReviewDocument,
) -> None:
    with SessionLocal() as db:
        try:
            db.add(
                AuditLog(
                    agent_id=document.agent_id,
                    actor_user_id=reviewer_user_id,
                    action="biometric_review_document_viewed",
                    details={
                        "check_id": str(check_id),
                        "document_id": str(document.document_id),
                        "document_type": document.document_type,
                        "outcome": "success",
                    },
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            raise


async def download_biometric_review_document(
    *,
    reviewer_user_id: uuid.UUID,
    check_id: uuid.UUID,
    document_id: uuid.UUID,
    storage: SupabaseStorageService,
) -> tuple[_PrivateReviewDocument, bytes]:
    """Serve one eligible review file only after authorization and audit."""

    document = await run_in_threadpool(
        _load_biometric_review_document_sync,
        reviewer_user_id,
        check_id,
        document_id,
    )
    if document.storage_bucket != storage.bucket:
        raise BiometricReviewRetrievalError(
            "Document storage configuration mismatch."
        )

    try:
        content = await storage.download(document.storage_path)
    except StorageOperationError as exc:
        raise BiometricReviewRetrievalError(
            "Biometric review document download failed."
        ) from exc

    try:
        await run_in_threadpool(
            _record_biometric_document_view_sync,
            reviewer_user_id,
            check_id,
            document,
        )
    except Exception as exc:
        raise BiometricReviewRetrievalError(
            "Biometric review document access could not be audited."
        ) from exc

    return document, content
