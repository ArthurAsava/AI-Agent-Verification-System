
from io import BytesIO
from unittest.mock import patch

import pymupdf as fitz
import pytest
from PIL import Image

from app.services.verification.ocr_service import (
    OCRProcessingError,
    extract_document_text,
)


def make_image():
    image = Image.new(
        "RGB",
        (200, 100),
        color="white",
    )

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_pdf(page_count=1):
    pdf = fitz.open()

    for index in range(page_count):
        page = pdf.new_page()
        page.insert_text(
            (50, 50),
            f"TEST DOCUMENT PAGE {index + 1}",
        )

    content = pdf.tobytes()
    pdf.close()

    return content


@patch(
    "app.services.verification.ocr_service."
    "pytesseract.image_to_string"
)
def test_extract_png_text(mock_ocr):
    mock_ocr.return_value = "TEST ID DOCUMENT"

    result = extract_document_text(
        make_image(),
        "image/png",
    )

    assert result.text == "TEST ID DOCUMENT"
    assert result.page_count == 1
    assert result.warnings == []


@patch(
    "app.services.verification.ocr_service."
    "pytesseract.image_to_string"
)
def test_extract_pdf_text(mock_ocr):
    mock_ocr.return_value = "TEST PDF TEXT"

    result = extract_document_text(
        make_pdf(),
        "application/pdf",
    )

    assert result.text == "TEST PDF TEXT"
    assert result.page_count == 1


@patch(
    "app.services.verification.ocr_service."
    "pytesseract.image_to_string"
)
def test_multiple_pdf_pages(mock_ocr):
    mock_ocr.return_value = "PAGE TEXT"

    result = extract_document_text(
        make_pdf(page_count=3),
        "application/pdf",
    )

    assert result.page_count == 3
    assert len(result.pages) == 3


def test_pdf_page_limit():
    with pytest.raises(OCRProcessingError):
        extract_document_text(
            make_pdf(page_count=6),
            "application/pdf",
        )


def test_invalid_document_rejected():
    with pytest.raises(OCRProcessingError):
        extract_document_text(
            b"invalid content",
            "image/png",
        )


@patch(
    "app.services.verification.ocr_service."
    "pytesseract.image_to_string"
)
def test_no_readable_text(mock_ocr):
    mock_ocr.return_value = ""

    result = extract_document_text(
        make_image(),
        "image/png",
    )

    assert "No readable text detected." in result.warnings


@patch(
    "app.services.verification.ocr_service."
    "pytesseract.image_to_string"
)
def test_ocr_timeout(mock_ocr):
    mock_ocr.side_effect = RuntimeError(
        "Tesseract process timeout"
    )

    with pytest.raises(OCRProcessingError):
        extract_document_text(
            make_image(),
            "image/png",
        )


@patch(
    "app.services.verification.ocr_service."
    "pytesseract.image_to_string"
)
def test_mime_mismatch_rejected(mock_ocr):
    with pytest.raises(OCRProcessingError):
        extract_document_text(
            make_image(),
            "image/jpeg",
        )

    mock_ocr.assert_not_called()
