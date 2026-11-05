
from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    Agent,
    AuditLog,
    DocumentStatus,
    KYCDocument,
)
from app.services.file_validation import validate_kyc_file
from app.services.storage_service import (
    StorageOperationError,
    SupabaseStorageService,
)


class AgentNotFoundError(ValueError):
    """Authenticated user has no agent profile."""


class InvalidDocumentTypeError(ValueError):
    """Unsupported KYC document type."""


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


@dataclass(frozen=True)
class UploadResult:
    document_id: uuid.UUID
    agent_id: uuid.UUID
    document_type: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    status: str


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
) -> None:
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

    audit_log = AuditLog(
        agent_id=agent_id,
        actor_user_id=user_id,
        action="kyc_document_uploaded",
        details={
            "document_id": str(document_id),
            "document_type": document_type,
            "mime_type": mime_type,
            "file_size_bytes": file_size_bytes,
        },
    )

    try:
        db.add(document)
        db.add(audit_log)
        db.commit()
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
) -> UploadResult:
    """Validate and register a private KYC document."""

    # 1. Validate document type.
    if document_type not in ALLOWED_DOCUMENT_TYPES:
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
    try:
        await run_in_threadpool(
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
    )
