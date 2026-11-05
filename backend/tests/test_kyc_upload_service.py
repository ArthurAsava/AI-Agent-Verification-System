
import io
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image

from app.services.kyc_upload_service import (
    AgentNotFoundError,
    InvalidDocumentTypeError,
    DocumentUploadError,
    upload_kyc_document,
)
from app.services.storage_service import (
    StorageOperationError,
)


def make_png() -> bytes:
    buffer = io.BytesIO()
    image = Image.new("RGB", (20, 20), "white")
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_db(agent):
    db = MagicMock()

    result = MagicMock()
    result.scalar_one_or_none.return_value = agent

    db.execute.return_value = result

    return db


def make_storage():
    storage = MagicMock()
    storage.bucket = "agent-kyc-documents"
    storage.upload = AsyncMock()
    storage.delete = AsyncMock()
    return storage


@pytest.mark.asyncio
async def test_successful_upload():
    user_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    agent = SimpleNamespace(
        id=agent_id,
        user_id=user_id,
    )

    db = make_db(agent)
    storage = make_storage()

    result = await upload_kyc_document(
        db=db,
        storage=storage,
        user_id=user_id,
        document_type="national_id_front",
        filename="id.png",
        content=make_png(),
        declared_content_type="image/png",
    )

    assert result.agent_id == agent_id
    assert result.status == "pending"

    storage.upload.assert_awaited_once()
    db.commit.assert_called_once()

    assert db.add.call_count == 2


@pytest.mark.asyncio
async def test_unregistered_agent_rejected():
    db = make_db(None)
    storage = make_storage()

    with pytest.raises(AgentNotFoundError):
        await upload_kyc_document(
            db=db,
            storage=storage,
            user_id=uuid.uuid4(),
            document_type="national_id_front",
            filename="id.png",
            content=make_png(),
        )

    storage.upload.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_document_type_rejected():
    db = make_db(None)
    storage = make_storage()

    with pytest.raises(InvalidDocumentTypeError):
        await upload_kyc_document(
            db=db,
            storage=storage,
            user_id=uuid.uuid4(),
            document_type="unknown_document",
            filename="id.png",
            content=make_png(),
        )

    storage.upload.assert_not_awaited()


@pytest.mark.asyncio
async def test_storage_failure_prevents_db_commit():
    user_id = uuid.uuid4()

    agent = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
    )

    db = make_db(agent)
    storage = make_storage()

    storage.upload.side_effect = StorageOperationError(
        "Simulated storage failure"
    )

    with pytest.raises(DocumentUploadError):
        await upload_kyc_document(
            db=db,
            storage=storage,
            user_id=user_id,
            document_type="national_id_front",
            filename="id.png",
            content=make_png(),
        )

    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_database_failure_triggers_cleanup():
    user_id = uuid.uuid4()

    agent = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
    )

    db = make_db(agent)
    db.commit.side_effect = RuntimeError(
        "Simulated database failure"
    )

    storage = make_storage()

    with pytest.raises(DocumentUploadError):
        await upload_kyc_document(
            db=db,
            storage=storage,
            user_id=user_id,
            document_type="national_id_front",
            filename="id.png",
            content=make_png(),
        )

    db.rollback.assert_called_once()
    storage.delete.assert_awaited_once()
