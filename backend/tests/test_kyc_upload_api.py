
from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import get_current_user
from app.core.database import get_db
from app.api.routes.kyc_documents import get_storage_service
from app.services.file_validation import MAX_FILE_SIZE
from app.services.kyc_upload_service import (
    AgentNotFoundError,
    DocumentCleanupError,
    DocumentUploadError,
    InvalidDocumentTypeError,
    UploadResult,
)
from app.services.storage_service import StorageConfigurationError


TEST_USER_ID = uuid.uuid4()
TEST_AGENT_ID = uuid.uuid4()
TEST_DOCUMENT_ID = uuid.uuid4()


@dataclass
class FakeUser:
    id: uuid.UUID


@pytest.fixture
def client():
    """
    Use an isolated FastAPI dependency configuration.

    No real database or Supabase Storage connection is made.
    """
    app.dependency_overrides[get_current_user] = (
        lambda: FakeUser(id=TEST_USER_ID)
    )
    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[get_storage_service] = lambda: MagicMock()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def valid_png():
    """Generate a genuine PNG entirely in memory."""
    from PIL import Image

    buffer = io.BytesIO()
    image = Image.new("RGB", (20, 20), "white")
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def upload(client, content=None, document_type="national_id_front"):
    if content is None:
        content = valid_png()

    return client.post(
        "/api/v1/kyc/documents",
        data={"document_type": document_type},
        files={
            "file": ("test.png", content, "image/png")
        },
    )


def test_upload_requires_authentication(client):
    app.dependency_overrides.pop(get_current_user, None)

    response = upload(client)

    assert response.status_code == 401


def test_rejects_oversized_file(client):
    content = b"x" * (MAX_FILE_SIZE + 1)

    response = upload(client, content=content)

    assert response.status_code == 413


def test_rejects_invalid_document_type(client, monkeypatch):
    async def fake_upload(**kwargs):
        raise InvalidDocumentTypeError(
            "Unsupported KYC document type."
        )

    monkeypatch.setattr(
        "app.api.routes.kyc_documents.upload_kyc_document",
        fake_upload,
    )

    response = upload(
        client,
        document_type="unsupported_document",
    )

    assert response.status_code == 422


def test_rejects_invalid_file_content(client, monkeypatch):
    from app.services.file_validation import FileValidationError

    async def fake_upload(**kwargs):
        raise FileValidationError("Invalid PNG file.")

    monkeypatch.setattr(
        "app.api.routes.kyc_documents.upload_kyc_document",
        fake_upload,
    )

    response = upload(client, content=b"not-a-real-png")

    assert response.status_code == 422


def test_agent_not_found(client, monkeypatch):
    async def fake_upload(**kwargs):
        raise AgentNotFoundError("Agent profile not found.")

    monkeypatch.setattr(
        "app.api.routes.kyc_documents.upload_kyc_document",
        fake_upload,
    )

    response = upload(client)

    assert response.status_code == 404


def test_storage_configuration_failure(client, monkeypatch):
    async def fake_upload(**kwargs):
        raise StorageConfigurationError(
            "Storage configuration unavailable."
        )

    monkeypatch.setattr(
        "app.api.routes.kyc_documents.upload_kyc_document",
        fake_upload,
    )

    response = upload(client)

    assert response.status_code == 503


def test_storage_upload_failure(client, monkeypatch):
    async def fake_upload(**kwargs):
        raise DocumentUploadError("Storage upload failed.")

    monkeypatch.setattr(
        "app.api.routes.kyc_documents.upload_kyc_document",
        fake_upload,
    )

    response = upload(client)

    assert response.status_code == 503


def test_database_metadata_failure(client, monkeypatch):
    async def fake_upload(**kwargs):
        raise DocumentUploadError(
            "Document metadata could not be saved."
        )

    monkeypatch.setattr(
        "app.api.routes.kyc_documents.upload_kyc_document",
        fake_upload,
    )

    response = upload(client)

    assert response.status_code == 503


def test_storage_cleanup_failure(client, monkeypatch):
    async def fake_upload(**kwargs):
        raise DocumentCleanupError(
            "Document cleanup failed."
        )

    monkeypatch.setattr(
        "app.api.routes.kyc_documents.upload_kyc_document",
        fake_upload,
    )

    response = upload(client)

    assert response.status_code == 500


def test_successful_authenticated_upload(client, monkeypatch):
    async def fake_upload(**kwargs):
        return UploadResult(
            document_id=TEST_DOCUMENT_ID,
            agent_id=TEST_AGENT_ID,
            document_type="national_id_front",
            original_filename="test.png",
            mime_type="image/png",
            file_size_bytes=len(valid_png()),
            status="pending",
        )

    monkeypatch.setattr(
        "app.api.routes.kyc_documents.upload_kyc_document",
        fake_upload,
    )

    response = upload(client)

    assert response.status_code == 201

    body = response.json()

    assert body["document_id"] == str(TEST_DOCUMENT_ID)
    assert body["agent_id"] == str(TEST_AGENT_ID)
    assert body["document_type"] == "national_id_front"
    assert body["original_filename"] == "test.png"
    assert body["mime_type"] == "image/png"
    assert body["status"] == "pending"
    assert body["file_size_bytes"] > 0
