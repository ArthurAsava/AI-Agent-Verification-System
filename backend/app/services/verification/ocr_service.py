
from __future__ import annotations

import os
from dataclasses import dataclass
from io import BytesIO

import pymupdf as fitz
import pytesseract
from PIL import Image, ImageOps
from pytesseract import TesseractError, TesseractNotFoundError

from app.services.verification.document_processor import (
    DocumentProcessingError,
    process_document,
)


MAX_PDF_PAGES = 5
MAX_RENDERED_PIXELS = 12_000_000
OCR_TIMEOUT_SECONDS = 20
PDF_RENDER_DPI = 150
MAX_EXTRACTED_CHARS = 20_000


class OCRProcessingError(RuntimeError):
    """Raised when OCR processing fails."""


@dataclass(frozen=True)
class OCRPageResult:
    page_number: int
    text: str


@dataclass(frozen=True)
class OCRResult:
    text: str
    page_count: int
    pages: list[OCRPageResult]
    warnings: list[str]
    engine_version: str = "tesseract-v1"


def _configure_tesseract() -> None:
    command = os.getenv("TESSERACT_CMD")

    if command:
        pytesseract.pytesseract.tesseract_cmd = command


def _extract_image_text(image: Image.Image) -> str:
    """
    Run OCR on an image.

    Tesseract is configured for English text and uses
    a timeout to limit individual OCR operations.
    """
    try:
        _configure_tesseract()

        normalized = ImageOps.exif_transpose(image)
        normalized = normalized.convert("RGB")

        text = pytesseract.image_to_string(
            normalized,
            lang="eng",
            config="--psm 3",
            timeout=OCR_TIMEOUT_SECONDS,
        )

        return text.strip()

    except (TesseractNotFoundError, TesseractError) as exc:
        raise OCRProcessingError(
            "OCR engine is unavailable or failed."
        ) from exc

    except RuntimeError as exc:
        raise OCRProcessingError(
            "OCR processing timed out or failed."
        ) from exc


def _extract_pdf_pages(content: bytes) -> list[OCRPageResult]:
    pages = []

    try:
        with fitz.open(stream=content, filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise OCRProcessingError(
                    "Password-protected PDFs are not supported."
                )

            if pdf.page_count < 1:
                raise OCRProcessingError(
                    "PDF contains no pages."
                )

            if pdf.page_count > MAX_PDF_PAGES:
                raise OCRProcessingError(
                    "PDF exceeds the maximum page count."
                )

            scale = PDF_RENDER_DPI / 72
            matrix = fitz.Matrix(scale, scale)

            for index in range(pdf.page_count):
                page = pdf.load_page(index)

                width = int(page.rect.width * scale + 1)
                height = int(page.rect.height * scale + 1)

                if width * height > MAX_RENDERED_PIXELS:
                    raise OCRProcessingError(
                        "PDF page dimensions exceed the limit."
                    )

                pixmap = page.get_pixmap(
                    matrix=matrix,
                    colorspace=fitz.csRGB,
                    alpha=False,
                )

                try:
                    image = Image.frombytes(
                        "RGB",
                        (pixmap.width, pixmap.height),
                        pixmap.samples,
                    )

                    text = _extract_image_text(image)
                finally:
                    del pixmap

                pages.append(
                    OCRPageResult(
                        page_number=index + 1,
                        text=text[:MAX_EXTRACTED_CHARS],
                    )
                )

    except OCRProcessingError:
        raise

    except (ValueError, RuntimeError, fitz.FileDataError) as exc:
        raise OCRProcessingError(
            "PDF could not be processed."
        ) from exc

    return pages


def extract_document_text(
    content: bytes,
    declared_mime_type: str,
) -> OCRResult:
    """
    Extract text from a previously uploaded KYC document.

    Does not persist extracted text or log document contents.
    """
    try:
        processed = process_document(
            content,
            declared_mime_type,
        )
    except DocumentProcessingError as exc:
        raise OCRProcessingError(
            "Document failed validation."
        ) from exc

    if processed.mime_type == "application/pdf":
        pages = _extract_pdf_pages(content)

    else:
        try:
            with Image.open(BytesIO(content)) as image:
                text = _extract_image_text(image)

            pages = [
                OCRPageResult(
                    page_number=1,
                    text=text[:MAX_EXTRACTED_CHARS],
                )
            ]

        except OCRProcessingError:
            raise

        except (OSError, ValueError) as exc:
            raise OCRProcessingError(
                "Image could not be processed."
            ) from exc

    combined_text = "\n".join(
        page.text for page in pages
    )[:MAX_EXTRACTED_CHARS]

    warnings = []

    if not combined_text.strip():
        warnings.append("No readable text detected.")

    return OCRResult(
        text=combined_text,
        page_count=len(pages),
        pages=pages,
        warnings=warnings,
    )
