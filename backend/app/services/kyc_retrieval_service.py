
from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.entities import Agent, KYCDocument, AuditLog
from app.services.storage_service import (
    StorageOperationError,
    SupabaseStorageService,
)


class DocumentNotFoundError(ValueError):
    pass


class DocumentRetrievalError(RuntimeError):
    pass


@dataclass(frozen=True)
class DocumentInfo:
    id: uuid.UUID
    agent_id: uuid.UUID
    document_type: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    status: str
    storage_path: str
    storage_bucket: str


def _to_info(document: KYCDocument) -> DocumentInfo:
    status_value = (
        document.status.value
        if hasattr(document.status, "value")
        else str(document.status)
    )

    return DocumentInfo(
        id=document.id,
        agent_id=document.agent_id,
        document_type=document.document_type,
        original_filename=document.original_filename,
        mime_type=document.mime_type,
        file_size_bytes=document.file_size_bytes,
        status=status_value,
        storage_path=document.storage_path,
        storage_bucket=document.storage_bucket,
    )


def _get_agent_id(db: Session, user_id: uuid.UUID) -> uuid.UUID:
    agent_id = db.execute(
        select(Agent.id).where(Agent.user_id == user_id)
    ).scalar_one_or_none()

    if agent_id is None:
        raise DocumentNotFoundError("Document not found.")

    return agent_id


def _list_documents_sync(user_id: uuid.UUID) -> list[DocumentInfo]:
    with SessionLocal() as db:
        agent_id = _get_agent_id(db, user_id)

        documents = db.execute(
            select(KYCDocument)
            .where(KYCDocument.agent_id == agent_id)
            .order_by(KYCDocument.id.desc())
        ).scalars().all()

        return [_to_info(document) for document in documents]


def _get_document_sync(
    user_id: uuid.UUID,
    document_id: uuid.UUID,
) -> DocumentInfo:
    with SessionLocal() as db:
        agent_id = _get_agent_id(db, user_id)

        document = db.execute(
            select(KYCDocument).where(
                KYCDocument.id == document_id,
                KYCDocument.agent_id == agent_id,
            )
        ).scalar_one_or_none()

        if document is None:
            raise DocumentNotFoundError("Document not found.")

        return _to_info(document)


async def list_agent_documents(
    user_id: uuid.UUID,
) -> list[DocumentInfo]:
    return await run_in_threadpool(
        _list_documents_sync,
        user_id,
    )


async def get_agent_document(
    user_id: uuid.UUID,
    document_id: uuid.UUID,
) -> DocumentInfo:
    return await run_in_threadpool(
        _get_document_sync,
        user_id,
        document_id,
    )


def _record_download_audit_sync(
    user_id: uuid.UUID,
    document: DocumentInfo,
) -> None:
    """Record a successful private KYC document retrieval."""

    with SessionLocal() as db:
        audit_log = AuditLog(
            agent_id=document.agent_id,
            actor_user_id=user_id,
            action="kyc_document_downloaded",
            details={
                "document_id": str(document.id),
                "document_type": document.document_type,
                "outcome": "success",
            },
        )

        try:
            db.add(audit_log)
            db.commit()
        except Exception:
            db.rollback()
            raise


async def download_agent_document(
    user_id: uuid.UUID,
    document_id: uuid.UUID,
    storage: SupabaseStorageService,
) -> tuple[DocumentInfo, bytes]:
    """Retrieve an authorized document and audit the access."""

    # 1. Verify document ownership.
    document = await get_agent_document(
        user_id=user_id,
        document_id=document_id,
    )

    # 2. Verify the configured Storage bucket.
    if document.storage_bucket != storage.bucket:
        raise DocumentRetrievalError(
            "Document storage configuration mismatch."
        )

    # 3. Retrieve the private document.
    try:
        content = await storage.download(
            document.storage_path
        )
    except StorageOperationError as exc:
        raise DocumentRetrievalError(
            "Document download failed."
        ) from exc

    # 4. Record the successful retrieval.
    try:
        await run_in_threadpool(
            _record_download_audit_sync,
            user_id,
            document,
        )
    except Exception as exc:
        raise DocumentRetrievalError(
            "Document access could not be audited."
        ) from exc

    # 5. Return the document only after audit persistence.
    return document, content

