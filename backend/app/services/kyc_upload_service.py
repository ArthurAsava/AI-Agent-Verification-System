
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    Agent,
    AuditLog,
    CheckStatus,
    DocumentStatus,
    KYCDocument,
    VerificationCheck,
)
from app.services.file_validation import (
    validate_biometric_selfie_file,
    validate_kyc_file,
)
from app.services.storage_service import (
    StorageOperationError,
    SupabaseStorageService,
)


class AgentNotFoundError(ValueError):
    """Authenticated user has no agent profile."""


class InvalidDocumentTypeError(ValueError):
    """Unsupported KYC document type."""


class BiometricConsentRequiredError(ValueError):
    """A selfie must never be retained without explicit consent."""


class DocumentUploadError(RuntimeError):
    """KYC upload could not be completed."""


class DocumentCleanupError(DocumentUploadError):
    """Database operation failed and cleanup failed."""


# Verify these identifiers against the existing
# GET /api/v1/kyc/requirements response.
ALLOWED_DOCUMENT_TYPES = frozenset({
    "national_id_front",
    "national_id_back",
    "passport",
    "proof_of_address",
})

BIOMETRIC_SELFIE_DOCUMENT_TYPE = "biometric_selfie"
BIOMETRIC_SELFIE_CHECK_TYPE = "biometric_selfie_capture"
BIOMETRIC_DIDIT_CHECK_TYPE = "biometric_didit_hosted_verification"


@dataclass(frozen=True)
class UploadResult:
    document_id: uuid.UUID
    agent_id: uuid.UUID
    document_type: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    status: str
    biometric_check_id: uuid.UUID | None = None


def _find_agent(
    db: Session,
    user_id: uuid.UUID,
) -> uuid.UUID:
    """Find the agent owned by the authenticated user."""

    agent = db.execute(
        select(Agent).where(Agent.user_id == user_id)
    ).scalar_one_or_none()

    if agent is None:
        raise AgentNotFoundError(
            "Complete agent registration before uploading "
            "KYC documents."
        )

    return agent.id


def _save_document_metadata(
    db: Session,
    *,
    document_id: uuid.UUID,
    agent_id: uuid.UUID,
    user_id: uuid.UUID,
    document_type: str,
    storage_path: str,
    storage_bucket: str,
    original_filename: str,
    mime_type: str,
    file_size_bytes: int,
    sha256_checksum: str,
    audit_action: str = "kyc_document_uploaded",
    audit_details: dict[str, Any] | None = None,
) -> uuid.UUID | None:
    """Persist document metadata and audit event."""

    document = KYCDocument(
        id=document_id,
        agent_id=agent_id,
        document_type=document_type,
        storage_path=storage_path,
        storage_bucket=storage_bucket,
        original_filename=original_filename,
        mime_type=mime_type,
        file_size_bytes=file_size_bytes,
        sha256_checksum=sha256_checksum,
        status=DocumentStatus.PENDING,
    )

    biometric_check: VerificationCheck | None = None
    if document_type == BIOMETRIC_SELFIE_DOCUMENT_TYPE:
        biometric_check = VerificationCheck(
            id=uuid.uuid4(),
            agent_id=agent_id,
            check_type=BIOMETRIC_SELFIE_CHECK_TYPE,
            status=CheckStatus.NEEDS_REVIEW,
            result_data={
                "selfie_document_id": str(document_id),
                "manual_review_required": True,
                "liveness_assessment": "manual_review_required",
                "face_match_assessment": "manual_review_required",
            },
        )

    details = {
        "document_id": str(document_id),
        "document_type": document_type,
        "mime_type": mime_type,
        "file_size_bytes": file_size_bytes,
    }
    if audit_details:
        details.update(audit_details)
    if biometric_check is not None:
        details["biometric_check_id"] = str(biometric_check.id)

    audit_log = AuditLog(
        agent_id=agent_id,
        actor_user_id=user_id,
        action=audit_action,
        details=details,
    )

    try:
        db.add(document)
        if biometric_check is not None:
            db.add(biometric_check)
        db.add(audit_log)
        db.commit()
        return biometric_check.id if biometric_check is not None else None
    except Exception:
        db.rollback()
        raise


async def upload_kyc_document(
    *,
    db: Session,
    storage: SupabaseStorageService,
    user_id: uuid.UUID,
    document_type: str,
    filename: str,
    content: bytes,
    declared_content_type: str | None = None,
    audit_action: str = "kyc_document_uploaded",
    audit_details: dict[str, Any] | None = None,
    allow_biometric_selfie: bool = False,
) -> UploadResult:
    """Validate and register a private KYC document."""

    # 1. Validate document type.
    if (
        document_type not in ALLOWED_DOCUMENT_TYPES
        and not (
            document_type == BIOMETRIC_SELFIE_DOCUMENT_TYPE
            and allow_biometric_selfie
        )
    ):
        raise InvalidDocumentTypeError(
            "Unsupported KYC document type."
        )

    # 2. Validate file contents.
    validated = await run_in_threadpool(
        validate_kyc_file,
        filename,
        content,
        declared_content_type,
    )

    if document_type == BIOMETRIC_SELFIE_DOCUMENT_TYPE:
        await run_in_threadpool(
            validate_biometric_selfie_file,
            validated,
        )

    # 3. Find the authenticated user's agent.
    agent_id = await run_in_threadpool(
        _find_agent,
        db,
        user_id,
    )

    # 4. Generate server-controlled identifiers.
    document_id = uuid.uuid4()

    storage_path = (
        f"{agent_id}/{document_id}/"
        f"document{validated.extension}"
    )

    # 5. Upload to private Supabase Storage.
    try:
        await storage.upload(
            path=storage_path,
            content=validated.content,
            content_type=validated.mime_type,
        )
    except StorageOperationError as exc:
        raise DocumentUploadError(
            "Unable to store the KYC document."
        ) from exc

    # 6. Persist metadata and audit event.
    biometric_check_id: uuid.UUID | None = None
    try:
        biometric_check_id = await run_in_threadpool(
            _save_document_metadata,
            db,
            document_id=document_id,
            agent_id=agent_id,
            user_id=user_id,
            document_type=document_type,
            storage_path=storage_path,
            storage_bucket=storage.bucket,
            original_filename=validated.original_filename,
            mime_type=validated.mime_type,
            file_size_bytes=validated.size_bytes,
            sha256_checksum=validated.sha256_checksum,
            audit_action=audit_action,
            audit_details=audit_details,
        )
    except Exception as exc:
        # Storage and PostgreSQL are separate systems.
        # Attempt compensating cleanup.
        try:
            await storage.delete(storage_path)
        except Exception as cleanup_exc:
            raise DocumentCleanupError(
                "Document registration failed and storage "
                "cleanup also failed."
            ) from cleanup_exc

        raise DocumentUploadError(
            "Document registration failed. "
            "Uploaded file was removed."
        ) from exc

    # 7. Return safe document metadata.
    return UploadResult(
        document_id=document_id,
        agent_id=agent_id,
        document_type=document_type,
        original_filename=validated.original_filename,
        mime_type=validated.mime_type,
        file_size_bytes=validated.size_bytes,
        status=DocumentStatus.PENDING.value,
        biometric_check_id=biometric_check_id,
    )


async def upload_biometric_selfie(
    *,
    db: Session,
    storage: SupabaseStorageService,
    user_id: uuid.UUID,
    consent: bool,
    filename: str,
    content: bytes,
    declared_content_type: str | None = None,
) -> UploadResult:
    """Store consented selfie evidence for a human biometric review.

    This function does not claim to perform liveness detection or face
    matching. It records only the minimum metadata needed for a later,
    secure human-review workflow.
    """

    if consent is not True:
        raise BiometricConsentRequiredError(
            "Explicit consent is required before capturing a biometric selfie."
        )

    return await upload_kyc_document(
        db=db,
        storage=storage,
        user_id=user_id,
        document_type=BIOMETRIC_SELFIE_DOCUMENT_TYPE,
        filename=filename,
        content=content,
        declared_content_type=declared_content_type,
        audit_action="biometric_selfie_captured",
        audit_details={
            "consent_recorded": True,
            "capture_source": "browser_camera",
            "liveness_assessment": "manual_review_required",
            "face_match_assessment": "manual_review_required",
        },
        allow_biometric_selfie=True,
    )
