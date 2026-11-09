
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, UnidentifiedImageError


MAX_FILE_SIZE = 5 * 1024 * 1024

SUPPORTED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "application/pdf",
}

# Limit decompressed image pixels to reduce resource abuse.
MAX_IMAGE_PIXELS = 20_000_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


class DocumentProcessingError(ValueError):
    """Raised when document processing fails."""


@dataclass(frozen=True)
class ProcessedDocument:
    mime_type: str
    file_size: int
    width: int | None = None
    height: int | None = None
    page_count: int | None = None


def _detect_mime_type(content: bytes) -> str:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    if content.startswith(b"%PDF-"):
        return "application/pdf"

    raise DocumentProcessingError(
        "Unsupported or unrecognized document format."
    )


def process_document(
    content: bytes,
    declared_mime_type: str,
) -> ProcessedDocument:
    """
    Validate document bytes before OCR processing.

    The declared MIME type must match the detected type.
    """

    if not content:
        raise DocumentProcessingError(
            "Document cannot be empty."
        )

    if len(content) > MAX_FILE_SIZE:
        raise DocumentProcessingError(
            "Document exceeds the 5 MB limit."
        )

    if declared_mime_type not in SUPPORTED_MIME_TYPES:
        raise DocumentProcessingError(
            "Unsupported MIME type."
        )

    detected_mime_type = _detect_mime_type(content)

    if detected_mime_type != declared_mime_type:
        raise DocumentProcessingError(
            "Document MIME type does not match its content."
        )

    if detected_mime_type in ("image/jpeg", "image/png"):
        try:
            with Image.open(BytesIO(content)) as image:
                if image.format not in ("JPEG", "PNG"):
                    raise DocumentProcessingError(
                        "Unsupported image format."
                    )

                width, height = image.size

                if width * height > MAX_IMAGE_PIXELS:
                    raise DocumentProcessingError(
                        "Image dimensions exceed the allowed limit."
                    )

                # Force Pillow to decode the image data.
                image.load()

                return ProcessedDocument(
                    mime_type=detected_mime_type,
                    file_size=len(content),
                    width=width,
                    height=height,
                    page_count=1,
                )

        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
        ) as exc:
            raise DocumentProcessingError(
                "Invalid or corrupted image."
            ) from exc

    # Preliminary PDF validation only.
    # Full structural parsing will be added in 8B.2.
    if b"%%EOF" not in content[-2048:]:
        raise DocumentProcessingError(
            "PDF appears incomplete or corrupted."
        )

    return ProcessedDocument(
        mime_type=detected_mime_type,
        file_size=len(content),
        page_count=None,
    )
