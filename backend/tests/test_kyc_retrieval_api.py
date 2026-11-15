
from __future__ import annotations

import uuid
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import get_current_user
from app.api.routes.kyc_documents import get_storage_service
from app.services.kyc_retrieval_service import (
    DocumentInfo,
    DocumentNotFoundError,
    DocumentRetrievalError,
)


USER_ID = uuid.uuid4()
AGENT_ID = uuid.uuid4()
DOCUMENT_ID = uuid.uuid4()


@dataclass
class FakeUser:
    id: uuid.UUID


@pytest.fixture
def client():
    previous_overrides = app.dependency_overrides.copy()

    app.dependency_overrides[get_current_user] = (
        lambda: FakeUser(id=USER_ID)
    )
    app.dependency_overrides[get_storage_service] = (
        lambda: MagicMock()
    )

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest.fixture
def document():
    return DocumentInfo(
        id=DOCUMENT_ID,
        agent_id=AGENT_ID,
        document_type="national_id_front",
        original_filename="test.png",
        mime_type="image/png",
        file_size_bytes=8,
        status="pending",
        storage_path=f"{AGENT_ID}/{DOCUMENT_ID}/document.png",
        storage_bucket="agent-kyc-documents",
    )


def test_listing_requires_authentication(client):
    app.dependency_overrides.pop(get_current_user)

    response = client.get("/api/v1/kyc/documents")

    assert response.status_code == 401


def test_metadata_requires_authentication(client):
    app.dependency_overrides.pop(get_current_user)

    response = client.get(
        f"/api/v1/kyc/documents/{DOCUMENT_ID}"
    )

    assert response.status_code == 401


def test_download_requires_authentication(client):
    app.dependency_overrides.pop(get_current_user)

    response = client.get(
        f"/api/v1/kyc/documents/{DOCUMENT_ID}/download"
    )

    assert response.status_code == 401


def test_list_documents_success(
    client, document, monkeypatch
):
    mock_service = AsyncMock(return_value=[document])

    monkeypatch.setattr(
        "app.api.routes.kyc_documents.list_agent_documents",
        mock_service,
    )

    response = client.get("/api/v1/kyc/documents")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["document_id"] == str(
        DOCUMENT_ID
    )

    mock_service.assert_awaited_once_with(USER_ID)


def test_get_document_success(
    client, document, monkeypatch
):
    mock_service = AsyncMock(return_value=document)

    monkeypatch.setattr(
        "app.api.routes.kyc_documents.get_agent_document",
        mock_service,
    )

    response = client.get(
        f"/api/v1/kyc/documents/{DOCUMENT_ID}"
    )

    assert response.status_code == 200
    assert response.json()["agent_id"] == str(AGENT_ID)

    mock_service.assert_awaited_once_with(
        USER_ID, DOCUMENT_ID
    )


def test_missing_document_returns_404(
    client, monkeypatch
):
    mock_service = AsyncMock(
        side_effect=DocumentNotFoundError(
            "Document not found."
        )
    )

    monkeypatch.setattr(
        "app.api.routes.kyc_documents.get_agent_document",
        mock_service,
    )

    response = client.get(
        f"/api/v1/kyc/documents/{DOCUMENT_ID}"
    )

    assert response.status_code == 404


def test_missing_download_returns_404(
    client, monkeypatch
):
    mock_service = AsyncMock(
        side_effect=DocumentNotFoundError(
            "Document not found."
        )
    )

    monkeypatch.setattr(
        "app.api.routes.kyc_documents.download_agent_document",
        mock_service,
    )

    response = client.get(
        f"/api/v1/kyc/documents/{DOCUMENT_ID}/download"
    )

    assert response.status_code == 404


def test_successful_download(
    client, document, monkeypatch
):
    content = b"\x89PNG\r\n\x1a\n"

    mock_service = AsyncMock(
        return_value=(document, content)
    )

    monkeypatch.setattr(
        "app.api.routes.kyc_documents.download_agent_document",
        mock_service,
    )

    response = client.get(
        f"/api/v1/kyc/documents/{DOCUMENT_ID}/download"
    )

    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "no-store"
    assert (
        response.headers["x-content-type-options"]
        == "nosniff"
    )
    assert "attachment" in response.headers[
        "content-disposition"
    ]

    assert mock_service.await_args.kwargs["user_id"] == USER_ID
    assert (
        mock_service.await_args.kwargs["document_id"]
        == DOCUMENT_ID
    )


def test_storage_failure_returns_503(
    client, monkeypatch
):
    mock_service = AsyncMock(
        side_effect=DocumentRetrievalError(
            "Document download failed."
        )
    )

    monkeypatch.setattr(
        "app.api.routes.kyc_documents.download_agent_document",
        mock_service,
    )

    response = client.get(
        f"/api/v1/kyc/documents/{DOCUMENT_ID}/download"
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Document download is unavailable."
    )


def test_invalid_document_uuid_returns_422(client):
    response = client.get(
        "/api/v1/kyc/documents/not-a-valid-uuid"
    )

    assert response.status_code == 422


def test_list_documents_without_agent_returns_404(
    client, monkeypatch
):
    mock_service = AsyncMock(
        side_effect=DocumentNotFoundError(
            "Document not found."
        )
    )

    monkeypatch.setattr(
        "app.api.routes.kyc_documents.list_agent_documents",
        mock_service,
    )

    response = client.get("/api/v1/kyc/documents")

    assert response.status_code == 404
