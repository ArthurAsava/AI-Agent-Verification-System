
from __future__ import annotations

import hashlib
import hmac
import re


class DocumentIntegrityError(ValueError):
    """Raised when document integrity cannot be established."""


def calculate_sha256(content: bytes) -> str:
    """Return the hexadecimal SHA-256 digest."""
    return hashlib.sha256(content).hexdigest()


def verify_document_integrity(
    *,
    content: bytes,
    expected_checksum: str | None,
) -> None:
    """
    Verify document bytes against the stored SHA-256 digest.

    Raises DocumentIntegrityError when verification fails.

    Does not log or return document contents.
    """

    if not isinstance(content, bytes):
        raise DocumentIntegrityError(
            "Document content must be bytes."
        )

    if not content:
        raise DocumentIntegrityError(
            "Document content is empty."
        )

    if not expected_checksum:
        raise DocumentIntegrityError(
            "Document checksum is unavailable."
        )

    expected = expected_checksum.strip().lower()

    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise DocumentIntegrityError(
            "Stored document checksum is invalid."
        )

    actual = calculate_sha256(content)

    if not hmac.compare_digest(actual, expected):
        raise DocumentIntegrityError(
            "Document integrity verification failed."
        )
