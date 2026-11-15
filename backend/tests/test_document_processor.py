
from io import BytesIO

import pytest
from PIL import Image

from app.services.verification.document_processor import (
    DocumentProcessingError,
    process_document,
)


def make_image(format_name="PNG"):
    image = Image.new(
        "RGB",
        (120, 80),
        color="white",
    )

    buffer = BytesIO()
    image.save(buffer, format=format_name)
    return buffer.getvalue()


def test_valid_png():
    content = make_image("PNG")

    result = process_document(
        content,
        "image/png",
    )

    assert result.mime_type == "image/png"
    assert result.width == 120
    assert result.height == 80
    assert result.page_count == 1


def test_valid_jpeg():
    content = make_image("JPEG")

    result = process_document(
        content,
        "image/jpeg",
    )

    assert result.mime_type == "image/jpeg"
    assert result.width == 120
    assert result.height == 80


def test_empty_document_rejected():
    with pytest.raises(DocumentProcessingError):
        process_document(
            b"",
            "image/png",
        )


def test_oversized_document_rejected():
    content = b"x" * (5 * 1024 * 1024 + 1)

    with pytest.raises(DocumentProcessingError):
        process_document(
            content,
            "image/png",
        )


def test_mime_type_mismatch_rejected():
    content = make_image("PNG")

    with pytest.raises(DocumentProcessingError):
        process_document(
            content,
            "image/jpeg",
        )


def test_invalid_image_rejected():
    content = b"\x89PNG\r\n\x1a\ninvalid"

    with pytest.raises(DocumentProcessingError):
        process_document(
            content,
            "image/png",
        )


def test_unsupported_file_rejected():
    with pytest.raises(DocumentProcessingError):
        process_document(
            b"plain text document",
            "text/plain",
        )


def test_preliminary_pdf_validation():
    content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n"
        b"<< /Type /Catalog >>\n"
        b"endobj\n"
        b"%%EOF"
    )

    result = process_document(
        content,
        "application/pdf",
    )

    assert result.mime_type == "application/pdf"
    assert result.page_count is None


def test_incomplete_pdf_rejected():
    content = b"%PDF-1.4\nincomplete"

    with pytest.raises(DocumentProcessingError):
        process_document(
            content,
            "application/pdf",
        )
