
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader


MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MiB
MIN_BIOMETRIC_SELFIE_DIMENSION = 320

ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}

ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


class FileValidationError(ValueError):
    """Raised when a KYC file fails validation."""


@dataclass(frozen=True)
class ValidatedFile:
    original_filename: str
    mime_type: str
    extension: str
    size_bytes: int
    sha256_checksum: str
    content: bytes


def validate_biometric_selfie_file(
    validated_file: ValidatedFile,
) -> None:
    """Apply the additional constraints for a selfie capture.

    A biometric selfie must be an image, never a PDF. This validates only
    basic capture quality; liveness and face matching require an approved
    provider or human reviewer.
    """

    if validated_file.mime_type not in {
        "image/jpeg",
        "image/png",
    }:
        raise FileValidationError(
            "A biometric selfie must be a JPEG or PNG image."
        )

    try:
        with Image.open(io.BytesIO(validated_file.content)) as image:
            width, height = image.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise FileValidationError(
            "The biometric selfie could not be decoded."
        ) from exc

    if min(width, height) < MIN_BIOMETRIC_SELFIE_DIMENSION:
        raise FileValidationError(
            "The biometric selfie must be at least "
            f"{MIN_BIOMETRIC_SELFIE_DIMENSION} pixels on each side."
        )


def detect_file_type(content: bytes) -> str:
    """Identify file format from its actual signature."""

    if content.startswith(b"%PDF-"):
        return "application/pdf"

    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    raise FileValidationError(
        "Unsupported file format. Upload a PDF, JPEG, or PNG."
    )


def validate_image(
    content: bytes,
    expected_mime_type: str,
) -> None:
    """Check image integrity and format."""

    try:
        with Image.open(io.BytesIO(content)) as image:
            actual_format = image.format
            image.verify()

        expected_format = {
            "image/jpeg": "JPEG",
            "image/png": "PNG",
        }[expected_mime_type]

        if actual_format != expected_format:
            raise FileValidationError(
                "Image content does not match its file format."
            )

        # Ensure pixel data can actually be decoded.
        with Image.open(io.BytesIO(content)) as image:
            image.load()

    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise FileValidationError(
            "The image is corrupted or invalid."
        ) from exc


def validate_pdf(content: bytes) -> None:
    """Check whether the PDF can be parsed."""

    try:
        reader = PdfReader(
            io.BytesIO(content),
            strict=True,
        )

        if reader.is_encrypted:
            raise FileValidationError(
                "Password-protected PDFs are not supported."
            )

        if len(reader.pages) == 0:
            raise FileValidationError(
                "The PDF must contain at least one page."
            )

        # Force parsing of the page content streams.
        for page in reader.pages:
            _ = page.get_contents()

    except FileValidationError:
        raise

    except Exception as exc:
        raise FileValidationError(
            "The PDF is corrupted or invalid."
        ) from exc


def validate_kyc_file(
    filename: str,
    content: bytes,
    declared_content_type: str | None = None,
) -> ValidatedFile:
    """
    Validate a KYC document before storage.

    Never trust filename extensions or browser MIME types
    without checking the file contents.
    """

    if not filename or not filename.strip():
        raise FileValidationError(
            "A filename is required."
        )

    # Prevent directory paths in filenames.
    normalized_filename = filename.replace("\\", "/")

    if "/" in normalized_filename:
        raise FileValidationError(
            "Filename must not contain directory paths."
        )

    if len(filename) > 255:
        raise FileValidationError(
            "Filename is too long."
        )

    if not isinstance(content, bytes):
        raise FileValidationError(
            "File content must be bytes."
        )

    size_bytes = len(content)

    if size_bytes == 0:
        raise FileValidationError(
            "The uploaded file is empty."
        )

    if size_bytes > MAX_FILE_SIZE:
        raise FileValidationError(
            "File exceeds the maximum allowed size of 5 MiB."
        )

    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            "Only PDF, JPG, JPEG, and PNG files are allowed."
        )

    detected_mime_type = detect_file_type(content)

    expected_mime_type = ALLOWED_EXTENSIONS[extension]

    if detected_mime_type != expected_mime_type:
        raise FileValidationError(
            "File extension does not match its actual format."
        )

    if declared_content_type:
        normalized_type = (
            declared_content_type.split(";")[0].strip().lower()
        )

        if normalized_type != detected_mime_type:
            raise FileValidationError(
                "Declared content type does not match file contents."
            )

    if detected_mime_type == "application/pdf":
        validate_pdf(content)
    else:
        validate_image(content, detected_mime_type)

    checksum = hashlib.sha256(content).hexdigest()

    return ValidatedFile(
        original_filename=filename,
        mime_type=detected_mime_type,
        extension=ALLOWED_MIME_TYPES[detected_mime_type],
        size_bytes=size_bytes,
        sha256_checksum=checksum,
        content=content,
    )
