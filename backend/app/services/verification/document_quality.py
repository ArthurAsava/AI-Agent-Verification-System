
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np
import pymupdf
from PIL import Image, ImageOps

from app.services.verification.document_processor import (
    DocumentProcessingError,
    process_document,
)
from app.services.verification.ocr_service import (
    OCRResult,
    MAX_PDF_PAGES,
    MAX_RENDERED_PIXELS,
    PDF_RENDER_DPI,
)


QUALITY_VERSION = "document-quality-v1"

MIN_WIDTH = 600
MIN_HEIGHT = 350
MIN_CONTRAST = 35.0
MIN_SHARPNESS = 50.0
MIN_TEXT_CHARS = 20
MAX_ANALYSIS_PIXELS = 1_000_000


class DocumentQualityError(ValueError):
    """Raised when document quality cannot be assessed."""


@dataclass(frozen=True)
class ImageQualityMetrics:
    width: int
    height: int
    brightness: float
    contrast: float
    sharpness: float


@dataclass(frozen=True)
class DocumentQualityResult:
    score: int
    status: str
    page_count: int
    metrics: list[ImageQualityMetrics]
    warnings: list[str]
    analyzer_version: str = QUALITY_VERSION


def _analyze_image(
    image: Image.Image,
) -> ImageQualityMetrics:
    """
    Calculate image quality metrics.

    Downsampling limits analysis memory and processing cost.
    """

    image = ImageOps.exif_transpose(image)
    width, height = image.size

    if width <= 0 or height <= 0:
        raise DocumentQualityError(
            "Invalid image dimensions."
        )

    image = image.convert("L")

    if width * height > MAX_ANALYSIS_PIXELS:
        scale = (
            MAX_ANALYSIS_PIXELS / (width * height)
        ) ** 0.5

        image = image.resize(
            (
                max(1, int(width * scale)),
                max(1, int(height * scale)),
            ),
            Image.Resampling.BILINEAR,
        )

    pixels = np.asarray(
        image,
        dtype=np.float32,
    )

    brightness = float(np.mean(pixels))
    contrast = float(np.std(pixels))

    # Variance of a discrete Laplacian approximation.
    # This is a heuristic sharpness measurement.
    if min(pixels.shape) < 3:
        sharpness = 0.0
    else:
        center = pixels[1:-1, 1:-1]

        laplacian = (
            -4 * center
            + pixels[:-2, 1:-1]
            + pixels[2:, 1:-1]
            + pixels[1:-1, :-2]
            + pixels[1:-1, 2:]
        )

        sharpness = float(np.var(laplacian))

    return ImageQualityMetrics(
        width=width,
        height=height,
        brightness=round(brightness, 2),
        contrast=round(contrast, 2),
        sharpness=round(sharpness, 2),
    )


def _load_document_images(
    content: bytes,
    mime_type: str,
) -> list[ImageQualityMetrics]:
    """
    Inspect image documents or render PDF pages.

    Only calculated metrics are retained.
    """

    metrics = []

    try:
        if mime_type in ("image/jpeg", "image/png"):
            with Image.open(BytesIO(content)) as image:
                image.load()
                metrics.append(_analyze_image(image))

        elif mime_type == "application/pdf":
            with pymupdf.open(
                stream=content,
                filetype="pdf",
            ) as pdf:

                if pdf.needs_pass:
                    raise DocumentQualityError(
                        "Password-protected PDF."
                    )

                if not 1 <= pdf.page_count <= MAX_PDF_PAGES:
                    raise DocumentQualityError(
                        "Unsupported PDF page count."
                    )

                scale = PDF_RENDER_DPI / 72
                matrix = pymupdf.Matrix(scale, scale)

                for page in pdf:
                    width = int(page.rect.width * scale + 1)
                    height = int(page.rect.height * scale + 1)

                    if width * height > MAX_RENDERED_PIXELS:
                        raise DocumentQualityError(
                            "PDF page dimensions exceed limit."
                        )

                    pixmap = page.get_pixmap(
                        matrix=matrix,
                        colorspace=pymupdf.csRGB,
                        alpha=False,
                    )

                    image = Image.frombytes(
                        "RGB",
                        (pixmap.width, pixmap.height),
                        pixmap.samples,
                    )

                    metrics.append(
                        _analyze_image(image)
                    )

    except DocumentQualityError:
        raise
    except (
        OSError,
        ValueError,
        RuntimeError,
        pymupdf.FileDataError,
    ) as exc:
        raise DocumentQualityError(
            "Document image analysis failed."
        ) from exc

    return metrics


def analyze_document_quality(
    content: bytes,
    mime_type: str,
    ocr_result: OCRResult,
) -> DocumentQualityResult:
    """
    Assess document readability using image and OCR signals.

    This function does not determine fraud or identity
    authenticity, and does not persist sensitive data.
    """

    try:
        process_document(content, mime_type)
    except DocumentProcessingError as exc:
        raise DocumentQualityError(
            "Document failed validation."
        ) from exc

    metrics = _load_document_images(
        content,
        mime_type,
    )

    if not metrics:
        raise DocumentQualityError(
            "No document pages could be analyzed."
        )

    if ocr_result.page_count != len(metrics):
        raise DocumentQualityError(
            "OCR page count does not match document."
        )

    score = 100
    warnings = []

    for index, item in enumerate(metrics, start=1):
        if (
            item.width < MIN_WIDTH
            or item.height < MIN_HEIGHT
        ):
            score -= 15
            warnings.append(
                f"Page {index}: Low image resolution."
            )

        if item.sharpness < MIN_SHARPNESS:
            score -= 15
            warnings.append(
                f"Page {index}: Possible image blur."
            )

        if item.contrast < MIN_CONTRAST:
            score -= 15
            warnings.append(
                f"Page {index}: Low image contrast."
            )

        if item.brightness < 45:
            score -= 10
            warnings.append(
                f"Page {index}: Image appears too dark."
            )

        elif item.brightness > 245:
            score -= 10
            warnings.append(
                f"Page {index}: Image appears too bright."
            )

    readable_chars = sum(
        character.isalnum()
        for character in ocr_result.text
    )

    if readable_chars < MIN_TEXT_CHARS:
        score -= 25
        warnings.append(
            "Insufficient readable OCR text."
        )

    warnings.extend(ocr_result.warnings)

    score = max(0, min(100, score))

    if score >= 80 and not warnings:
        status = "pass"
    else:
        status = "needs_review"

    return DocumentQualityResult(
        score=score,
        status=status,
        page_count=len(metrics),
        metrics=metrics,
        warnings=warnings,
    )
