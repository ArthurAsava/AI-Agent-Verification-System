
from __future__ import annotations

import pytest

from app.services.file_validation import (
    FileValidationError,
    MAX_FILE_SIZE,
    validate_kyc_file,
)



@pytest.mark.parametrize(
    "filename,mime_type,content",
    [
        (
            "identity.png",
            "image/png",
            b"not a real PNG",
        ),
        (
            "identity.pdf",
            "application/pdf",
            b"not a real PDF",
        ),
        (
            "identity.jpg",
            "image/jpeg",
            b"not a real JPEG",
        ),
        (
            "identity.exe",
            "application/octet-stream",
            b"MZ" + b"\x00" * 20,
        ),
        (
            "empty.pdf",
            "application/pdf",
            b"",
        ),
        (
            "oversized.pdf",
            "application/pdf",
            b"%PDF-1.4\n" + b"x" * MAX_FILE_SIZE,
        ),
    ],
    ids=[
        "fake-png",
        "fake-pdf",
        "fake-jpeg",
        "executable",
        "empty-file",
        "oversized-file",
    ],
)

def test_invalid_files_are_rejected(
    filename,
    mime_type,
    content,
):
    with pytest.raises(FileValidationError):
        validate_kyc_file(
            filename=filename,
            content=content,
            declared_content_type=mime_type,
        )


@pytest.mark.parametrize(
    "filename",
    [
        "../identity.pdf",
        "folder/identity.pdf",
        r"folder\identity.pdf",
    ],
)
def test_filename_paths_are_rejected(filename):
    with pytest.raises(FileValidationError):
        validate_kyc_file(
            filename=filename,
            content=b"%PDF-1.4",
            declared_content_type="application/pdf",
        )


def test_mismatched_file_signature_is_rejected():
    with pytest.raises(FileValidationError):
        validate_kyc_file(
            filename="identity.png",
            content=b"%PDF-1.4\n",
            declared_content_type="image/png",
        )
