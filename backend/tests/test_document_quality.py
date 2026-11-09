
from io import BytesIO

import numpy as np
import pymupdf
import pytest
from PIL import Image

from app.services.verification.document_quality import (
    DocumentQualityError,
    analyze_document_quality,
)

from app.services.verification.ocr_service import (
    OCRPageResult,
    OCRResult,
)


SAMPLE_TEXT = (
    "REPUBLIC OF KENYA NATIONAL IDENTITY CARD "
    "ID NUMBER 12345678 JOHN KAMAU MWANGI"
)


def make_ocr(text=SAMPLE_TEXT, page_count=1):
    return OCRResult(
        text=text,
        page_count=page_count,
        pages=[
            OCRPageResult(
                page_number=i + 1,
                text=text,
            )
            for i in range(page_count)
        ],
        warnings=[],
    )


def make_image(
    width=1000,
    height=600,
    mode="normal",
):
    rng = np.random.default_rng(42)

    if mode == "dark":
        array = np.full(
            (height, width),
            10,
            dtype=np.uint8,
        )

    elif mode == "bright":
        array = np.full(
            (height, width),
            255,
            dtype=np.uint8,
        )

    elif mode == "blurred":
        array = np.full(
            (height, width),
            128,
            dtype=np.uint8,
        )

    elif mode == "low_contrast":
        array = rng.integers(
            120,
            131,
            size=(height, width),
            dtype=np.uint8,
        )

    else:
        array = rng.integers(
            0,
            256,
            size=(height, width),
            dtype=np.uint8,
        )

    image = Image.fromarray(array)

    buffer = BytesIO()
    image.save(buffer, format="PNG")

    return buffer.getvalue()


def make_pdf():
    pdf = pymupdf.open()
    page = pdf.new_page()

    page.insert_text(
        (50, 80),
        SAMPLE_TEXT,
    )

    content = pdf.tobytes()
    pdf.close()

    return content


def test_good_quality_image():
    result = analyze_document_quality(
        make_image(),
        "image/png",
        make_ocr(),
    )

    assert result.score == 100
    assert result.status == "pass"
    assert result.page_count == 1


def test_low_resolution_detected():
    result = analyze_document_quality(
        make_image(width=300, height=200),
        "image/png",
        make_ocr(),
    )

    assert any(
        "Low image resolution" in warning
        for warning in result.warnings
    )


def test_dark_image_detected():
    result = analyze_document_quality(
        make_image(mode="dark"),
        "image/png",
        make_ocr(),
    )

    assert any(
        "too dark" in warning
        for warning in result.warnings
    )


def test_bright_image_detected():
    result = analyze_document_quality(
        make_image(mode="bright"),
        "image/png",
        make_ocr(),
    )

    assert any(
        "too bright" in warning
        for warning in result.warnings
    )


def test_low_contrast_detected():
    result = analyze_document_quality(
        make_image(mode="low_contrast"),
        "image/png",
        make_ocr(),
    )

    assert any(
        "Low image contrast" in warning
        for warning in result.warnings
    )


def test_possible_blur_detected():
    result = analyze_document_quality(
        make_image(mode="blurred"),
        "image/png",
        make_ocr(),
    )

    assert any(
        "Possible image blur" in warning
        for warning in result.warnings
    )


def test_insufficient_ocr_text():
    result = analyze_document_quality(
        make_image(),
        "image/png",
        make_ocr(text="ABC"),
    )

    assert result.status == "needs_review"
    assert "Insufficient readable OCR text." in result.warnings


def test_invalid_document_rejected():
    with pytest.raises(DocumentQualityError):
        analyze_document_quality(
            b"invalid",
            "image/png",
            make_ocr(),
        )


def test_pdf_quality_analysis():
    result = analyze_document_quality(
        make_pdf(),
        "application/pdf",
        make_ocr(),
    )

    assert result.page_count == 1
    assert len(result.metrics) == 1


def test_ocr_page_count_mismatch():
    with pytest.raises(DocumentQualityError):
        analyze_document_quality(
            make_image(),
            "image/png",
            make_ocr(page_count=2),
        )


def test_quality_score_bounded():
    result = analyze_document_quality(
        make_image(
            width=300,
            height=200,
            mode="dark",
        ),
        "image/png",
        make_ocr(text=""),
    )

    assert 0 <= result.score <= 100
    assert result.status == "needs_review"
