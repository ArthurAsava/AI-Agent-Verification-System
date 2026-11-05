
import hashlib
import io

import pytest
from PIL import Image
from pypdf import PdfWriter

from app.services.file_validation import (
    FileValidationError,
    MAX_FILE_SIZE,
    validate_kyc_file,
)


def make_image(image_format: str) -> bytes:
    buffer = io.BytesIO()

    image = Image.new(
        "RGB",
        (100, 100),
        color="white",
    )

    image.save(buffer, format=image_format)

    return buffer.getvalue()


def make_pdf() -> bytes:
    buffer = io.BytesIO()

    writer = PdfWriter()
    writer.add_blank_page(
        width=612,
        height=792,
    )

    writer.write(buffer)

    return buffer.getvalue()


def test_valid_jpeg():
    content = make_image("JPEG")

    result = validate_kyc_file(
        filename="national_id.jpg",
        content=content,
        declared_content_type="image/jpeg",
    )

    assert result.mime_type == "image/jpeg"
    assert result.extension == ".jpg"
    assert result.size_bytes == len(content)


def test_valid_png():
    content = make_image("PNG")

    result = validate_kyc_file(
        filename="passport.png",
        content=content,
        declared_content_type="image/png",
    )

    assert result.mime_type == "image/png"
    assert result.extension == ".png"


def test_valid_pdf():
    content = make_pdf()

    result = validate_kyc_file(
        filename="document.pdf",
        content=content,
        declared_content_type="application/pdf",
    )

    assert result.mime_type == "application/pdf"
    assert result.extension == ".pdf"


def test_sha256_checksum():
    content = make_image("PNG")

    result = validate_kyc_file(
        filename="document.png",
        content=content,
    )

    expected = hashlib.sha256(content).hexdigest()

    assert result.sha256_checksum == expected


def test_empty_file_rejected():
    with pytest.raises(FileValidationError):
        validate_kyc_file(
            filename="empty.pdf",
            content=b"",
        )


def test_oversized_file_rejected():
    content = b"A" * (MAX_FILE_SIZE + 1)

    with pytest.raises(
        FileValidationError,
        match="maximum allowed size",
    ):
        validate_kyc_file(
            filename="large.pdf",
            content=content,
        )


def test_wrong_extension_rejected():
    content = make_image("PNG")

    with pytest.raises(FileValidationError):
        validate_kyc_file(
            filename="document.exe",
            content=content,
        )


def test_spoofed_extension_rejected():
    content = make_image("PNG")

    with pytest.raises(FileValidationError):
        validate_kyc_file(
            filename="document.pdf",
            content=content,
        )


def test_mime_type_mismatch_rejected():
    content = make_image("JPEG")

    with pytest.raises(FileValidationError):
        validate_kyc_file(
            filename="document.jpg",
            content=content,
            declared_content_type="application/pdf",
        )


def test_corrupted_pdf_rejected():
    content = b"%PDF-1.7\ninvalid-pdf-content"

    with pytest.raises(FileValidationError):
        validate_kyc_file(
            filename="broken.pdf",
            content=content,
        )


def test_corrupted_png_rejected():
    content = b"\x89PNG\r\n\x1a\ncorrupted"

    with pytest.raises(FileValidationError):
        validate_kyc_file(
            filename="broken.png",
            content=content,
        )


def test_filename_path_rejected():
    content = make_image("PNG")

    with pytest.raises(FileValidationError):
        validate_kyc_file(
            filename="../passport.png",
            content=content,
        )


def test_missing_filename_rejected():
    content = make_image("PNG")

    with pytest.raises(FileValidationError):
        validate_kyc_file(
            filename="",
            content=content,
        )


def test_password_protected_pdf_rejected():
    buffer = io.BytesIO()

    writer = PdfWriter()
    writer.add_blank_page(
        width=612,
        height=792,
    )
    writer.encrypt("test-password")
    writer.write(buffer)

    with pytest.raises(
        FileValidationError,
        match="Password-protected",
    ):
        validate_kyc_file(
            filename="encrypted.pdf",
            content=buffer.getvalue(),
        )
