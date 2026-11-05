
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import kyc_retrieval_service as service


USER_ID = uuid.uuid4()
AGENT_ID = uuid.uuid4()
OTHER_AGENT_ID = uuid.uuid4()
DOCUMENT_ID = uuid.uuid4()


def fake_document(agent_id=AGENT_ID):
    document = MagicMock()

    document.id = DOCUMENT_ID
    document.agent_id = agent_id
    document.document_type = "national_id_front"
    document.original_filename = "test.png"
    document.mime_type = "image/png"
    document.file_size_bytes = 8
    document.status = "pending"
    document.storage_path = (
        f"{agent_id}/{DOCUMENT_ID}/document.png"
    )
    document.storage_bucket = "agent-kyc-documents"

    return document


def make_db(monkeypatch):
    db = MagicMock()
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = db

    monkeypatch.setattr(
        service,
        "SessionLocal",
        session_factory,
    )

    return db


def compiled_query(statement):
    return str(statement.compile()).lower()


def test_missing_agent_is_rejected(monkeypatch):
    db = make_db(monkeypatch)

    db.execute.return_value.scalar_one_or_none.return_value = None

    with pytest.raises(service.DocumentNotFoundError):
        service._get_document_sync(
            USER_ID,
            DOCUMENT_ID,
        )

    assert db.execute.call_count == 1


def test_document_query_checks_agent_ownership(monkeypatch):
    db = make_db(monkeypatch)

    agent_result = MagicMock()
    agent_result.scalar_one_or_none.return_value = AGENT_ID

    document_result = MagicMock()
    document_result.scalar_one_or_none.return_value = (
        fake_document()
    )

    db.execute.side_effect = [
        agent_result,
        document_result,
    ]

    result = service._get_document_sync(
        USER_ID,
        DOCUMENT_ID,
    )

    assert result.id == DOCUMENT_ID
    assert result.agent_id == AGENT_ID

    assert db.execute.call_count == 2

    agent_query = db.execute.call_args_list[0].args[0]
    document_query = db.execute.call_args_list[1].args[0]

    agent_sql = compiled_query(agent_query)
    document_sql = compiled_query(document_query)

    assert "user_id" in agent_sql
    assert "agent_id" in document_sql
    assert "kyc_documents.id" in document_sql

    document_params = document_query.compile().params

    assert AGENT_ID in document_params.values()
    assert DOCUMENT_ID in document_params.values()


def test_other_agents_document_is_not_returned(
    monkeypatch,
):
    db = make_db(monkeypatch)

    agent_result = MagicMock()
    agent_result.scalar_one_or_none.return_value = AGENT_ID

    # Simulates the database returning no matching row
    # when the document belongs to another agent.
    document_result = MagicMock()
    document_result.scalar_one_or_none.return_value = None

    db.execute.side_effect = [
        agent_result,
        document_result,
    ]

    with pytest.raises(service.DocumentNotFoundError):
        service._get_document_sync(
            USER_ID,
            DOCUMENT_ID,
        )

    document_query = db.execute.call_args_list[1].args[0]
    params = document_query.compile().params

    assert AGENT_ID in params.values()
    assert DOCUMENT_ID in params.values()
    assert OTHER_AGENT_ID not in params.values()


def test_list_query_filters_by_agent(monkeypatch):
    db = make_db(monkeypatch)

    agent_result = MagicMock()
    agent_result.scalar_one_or_none.return_value = AGENT_ID

    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = [
        fake_document()
    ]

    db.execute.side_effect = [
        agent_result,
        list_result,
    ]

    documents = service._list_documents_sync(USER_ID)

    assert len(documents) == 1
    assert documents[0].agent_id == AGENT_ID

    list_query = db.execute.call_args_list[1].args[0]
    list_sql = compiled_query(list_query)
    list_params = list_query.compile().params

    assert "agent_id" in list_sql
    assert AGENT_ID in list_params.values()


@pytest.mark.asyncio
async def test_download_checks_ownership_before_storage(
    monkeypatch,
):
    storage = MagicMock()
    storage.bucket = "agent-kyc-documents"
    storage.download = AsyncMock()

    mock_get = AsyncMock(
        side_effect=service.DocumentNotFoundError(
            "Document not found."
        )
    )

    monkeypatch.setattr(
        service,
        "get_agent_document",
        mock_get,
    )

    with pytest.raises(service.DocumentNotFoundError):
        await service.download_agent_document(
            USER_ID,
            DOCUMENT_ID,
            storage,
        )

    storage.download.assert_not_awaited()


@pytest.mark.asyncio
async def test_download_rejects_bucket_mismatch(
    monkeypatch,
):
    document = service.DocumentInfo(
        id=DOCUMENT_ID,
        agent_id=AGENT_ID,
        document_type="national_id_front",
        original_filename="test.png",
        mime_type="image/png",
        file_size_bytes=8,
        status="pending",
        storage_path="test/document.png",
        storage_bucket="unexpected-bucket",
    )

    storage = MagicMock()
    storage.bucket = "agent-kyc-documents"
    storage.download = AsyncMock()

    monkeypatch.setattr(
        service,
        "get_agent_document",
        AsyncMock(return_value=document),
    )

    with pytest.raises(service.DocumentRetrievalError):
        await service.download_agent_document(
            USER_ID,
            DOCUMENT_ID,
            storage,
        )

    storage.download.assert_not_awaited()


@pytest.mark.asyncio
async def test_authorized_download_uses_stored_path(
    monkeypatch,
):
    document = service.DocumentInfo(
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

    storage = MagicMock()
    storage.bucket = "agent-kyc-documents"
    storage.download = AsyncMock(
        return_value=b"\x89PNG\r\n\x1a\n"
    )

    monkeypatch.setattr(
        service,
        "get_agent_document",
        AsyncMock(return_value=document),
    )

    returned_document, content = (
        await service.download_agent_document(
            USER_ID,
            DOCUMENT_ID,
            storage,
        )
    )

    assert returned_document.id == DOCUMENT_ID
    assert content == b"\x89PNG\r\n\x1a\n"

    storage.download.assert_awaited_once_with(
        document.storage_path
    )
