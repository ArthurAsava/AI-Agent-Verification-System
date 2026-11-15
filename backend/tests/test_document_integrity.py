
import hashlib

import pytest

from app.services.verification.document_integrity import (
    DocumentIntegrityError,
    calculate_sha256,
    verify_document_integrity,
)


SAMPLE_CONTENT = b"synthetic identity document"


def test_sha256_calculation():
    expected = hashlib.sha256(
        SAMPLE_CONTENT
    ).hexdigest()

    assert calculate_sha256(SAMPLE_CONTENT) == expected


def test_matching_checksum_accepted():
    checksum = calculate_sha256(SAMPLE_CONTENT)

    verify_document_integrity(
        content=SAMPLE_CONTENT,
        expected_checksum=checksum,
    )


def test_modified_content_rejected():
    checksum = calculate_sha256(SAMPLE_CONTENT)

    with pytest.raises(DocumentIntegrityError):
        verify_document_integrity(
            content=b"modified identity document",
            expected_checksum=checksum,
        )


def test_missing_checksum_rejected():
    with pytest.raises(DocumentIntegrityError):
        verify_document_integrity(
            content=SAMPLE_CONTENT,
            expected_checksum=None,
        )


def test_malformed_checksum_rejected():
    with pytest.raises(DocumentIntegrityError):
        verify_document_integrity(
            content=SAMPLE_CONTENT,
            expected_checksum="invalid",
        )


def test_empty_document_rejected():
    with pytest.raises(DocumentIntegrityError):
        verify_document_integrity(
            content=b"",
            expected_checksum=calculate_sha256(b""),
        )


def test_uppercase_checksum_accepted():
    checksum = calculate_sha256(
        SAMPLE_CONTENT
    ).upper()

    verify_document_integrity(
        content=SAMPLE_CONTENT,
        expected_checksum=checksum,
    )


def test_wrong_content_type_rejected():
    with pytest.raises(DocumentIntegrityError):
        verify_document_integrity(
            content="not bytes",
            expected_checksum=calculate_sha256(
                SAMPLE_CONTENT
            ),
        )
