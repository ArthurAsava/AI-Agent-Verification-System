import io
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image

from app.models.entities import AuditLog, CheckStatus, VerificationCheck
from app.services.file_validation import (
    FileValidationError,
    validate_biometric_selfie_file,
    validate_kyc_file,
)
from app.services.kyc_upload_service import (
    BiometricConsentRequiredError,
    InvalidDocumentTypeError,
    upload_biometric_selfie,
    upload_kyc_document,
)


def make_png(size: int = 320) -> bytes:
    buffer = io.BytesIO()
    image = Image.new("RGB", (size, size), "white")
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


def test_biometric_selfie_requires_image_dimensions():
    small_image = validate_kyc_file(
        filename="selfie.png",
        content=make_png(319),
        declared_content_type="image/png",
    )

    with pytest.raises(FileValidationError, match="320"):
        validate_biometric_selfie_file(small_image)


@pytest.mark.asyncio
async def test_biometric_selfie_records_consent_and_manual_review():
    user_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    db = make_db(SimpleNamespace(id=agent_id, user_id=user_id))
    storage = make_storage()

    result = await upload_biometric_selfie(
        db=db,
        storage=storage,
        user_id=user_id,
        consent=True,
        filename="selfie.png",
        content=make_png(),
        declared_content_type="image/png",
    )

    assert result.document_type == "biometric_selfie"
    storage.upload.assert_awaited_once()

    audit = next(
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], AuditLog)
    )
    assert audit.action == "biometric_selfie_captured"
    assert audit.details["consent_recorded"] is True
    assert audit.details["liveness_assessment"] == "manual_review_required"
    assert audit.details["face_match_assessment"] == "manual_review_required"

    check = next(
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], VerificationCheck)
    )
    assert check.check_type == "biometric_selfie_capture"
    assert check.status == CheckStatus.NEEDS_REVIEW
    assert check.result_data["selfie_document_id"] == str(result.document_id)
    assert audit.details["biometric_check_id"] == str(check.id)


@pytest.mark.asyncio
async def test_biometric_selfie_rejects_missing_consent():
    storage = make_storage()

    with pytest.raises(BiometricConsentRequiredError):
        await upload_biometric_selfie(
            db=MagicMock(),
            storage=storage,
            user_id=uuid.uuid4(),
            consent=False,
            filename="selfie.png",
            content=make_png(),
            declared_content_type="image/png",
        )

    storage.upload.assert_not_awaited()


@pytest.mark.asyncio
async def test_generic_upload_cannot_bypass_biometric_consent():
    storage = make_storage()

    with pytest.raises(InvalidDocumentTypeError):
        await upload_kyc_document(
            db=MagicMock(),
            storage=storage,
            user_id=uuid.uuid4(),
            document_type="biometric_selfie",
            filename="selfie.png",
            content=make_png(),
            declared_content_type="image/png",
        )

    storage.upload.assert_not_awaited()
