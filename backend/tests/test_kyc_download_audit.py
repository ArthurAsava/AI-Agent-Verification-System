
import uuid
from unittest.mock import AsyncMock, patch
from unittest.mock import MagicMock

from app.models.entities import AuditLog
from app.services import kyc_retrieval_service as service

import pytest

from app.services.kyc_retrieval_service import (
    DocumentInfo,
    DocumentNotFoundError,
    DocumentRetrievalError,
    download_agent_document,
)


@pytest.fixture
def sample_document():
    return DocumentInfo(
        id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        document_type="passport",
        original_filename="test.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        status="pending",
        storage_path="agent/document/document.pdf",
        storage_bucket="agent-kyc-documents",
    )


@pytest.mark.asyncio
async def test_successful_download_records_audit(
    sample_document,
):
    user_id = uuid.uuid4()

    storage = AsyncMock()
    storage.bucket = "agent-kyc-documents"
    storage.download.return_value = b"test-content"

    with (
        patch(
            "app.services.kyc_retrieval_service."
            "get_agent_document",
            new_callable=AsyncMock,
            return_value=sample_document,
        ),
        patch(
            "app.services.kyc_retrieval_service."
            "_record_download_audit_sync"
        ) as audit,
    ):
        document, content = await download_agent_document(
            user_id=user_id,
            document_id=sample_document.id,
            storage=storage,
        )

        assert document.id == sample_document.id
        assert content == b"test-content"

        audit.assert_called_once_with(
            user_id,
            sample_document,
        )


@pytest.mark.asyncio
async def test_unauthorized_download_is_not_audited(
    sample_document,
):
    storage = AsyncMock()
    storage.bucket = "agent-kyc-documents"

    with (
        patch(
            "app.services.kyc_retrieval_service."
            "get_agent_document",
            new_callable=AsyncMock,
            side_effect=DocumentNotFoundError(
                "Document not found."
            ),
        ),
        patch(
            "app.services.kyc_retrieval_service."
            "_record_download_audit_sync"
        ) as audit,
    ):
        with pytest.raises(DocumentNotFoundError):
            await download_agent_document(
                user_id=uuid.uuid4(),
                document_id=sample_document.id,
                storage=storage,
            )

        storage.download.assert_not_called()
        audit.assert_not_called()


@pytest.mark.asyncio
async def test_audit_failure_prevents_download_response(
    sample_document,
):
    storage = AsyncMock()
    storage.bucket = "agent-kyc-documents"
    storage.download.return_value = b"test-content"

    with (
        patch(
            "app.services.kyc_retrieval_service."
            "get_agent_document",
            new_callable=AsyncMock,
            return_value=sample_document,
        ),
        patch(
            "app.services.kyc_retrieval_service."
            "_record_download_audit_sync",
            side_effect=RuntimeError(
                "Database unavailable"
            ),
        ),
    ):
        with pytest.raises(DocumentRetrievalError):
            await download_agent_document(
                user_id=uuid.uuid4(),
                document_id=sample_document.id,
                storage=storage,
            )


def test_download_audit_persists_expected_fields(
    sample_document,
    monkeypatch,
):
    user_id = uuid.uuid4()

    # Mock the database session.
    db = MagicMock()

    # Support: with SessionLocal() as db:
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = db

    monkeypatch.setattr(
        service,
        "SessionLocal",
        session_factory,
    )

    # Execute the real audit helper against a mocked session.
    service._record_download_audit_sync(
        user_id,
        sample_document,
    )

    # Verify a database record was added.
    db.add.assert_called_once()

    audit_record = db.add.call_args.args[0]

    assert isinstance(audit_record, AuditLog)
    assert audit_record.agent_id == sample_document.agent_id
    assert audit_record.actor_user_id == user_id
    assert audit_record.action == "kyc_document_downloaded"

    # Verify only approved metadata is recorded.
    assert audit_record.details == {
        "document_id": str(sample_document.id),
        "document_type": sample_document.document_type,
        "outcome": "success",
    }

    assert "storage_path" not in audit_record.details
    assert "original_filename" not in audit_record.details
    assert "sha256_checksum" not in audit_record.details

    # Verify transaction commit.
    db.commit.assert_called_once()


def test_download_audit_rolls_back_on_database_failure(
    sample_document,
    monkeypatch,
):
    user_id = uuid.uuid4()

    db = MagicMock()
    db.commit.side_effect = RuntimeError(
        "Simulated database failure"
    )

    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = db

    monkeypatch.setattr(
        service,
        "SessionLocal",
        session_factory,
    )

    with pytest.raises(
        RuntimeError,
        match="Simulated database failure",
    ):
        service._record_download_audit_sync(
            user_id,
            sample_document,
        )

    db.rollback.assert_called_once()
