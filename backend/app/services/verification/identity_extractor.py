
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from app.services.verification.ocr_service import OCRResult


EXTRACTOR_VERSION = "identity-extractor-v1"

SUPPORTED_DOCUMENT_TYPES = {
    "national_id",
    "passport",
}

ID_LABELS = (
    r"(?:ID\s*(?:NO\.?|NUMBER|NUM\.?)|"
    r"IDENTITY\s*(?:NO\.?|NUMBER)|"
    r"SERIAL\s*NUMBER)"
)

NAME_LABELS = (
    r"(?:FULL\s*NAME|"
    r"NAME|"
    r"NAMES)"
)

DOB_LABELS = (
    r"(?:DATE\s*OF\s*BIRTH|"
    r"DATE\s*OF\s*BIRTH\s*/\s*DOB|"
    r"DOB|"
    r"BIRTH\s*DATE)"
)

SEX_LABELS = r"(?:SEX|GENDER)"


class IdentityExtractionError(ValueError):
    """Raised when identity extraction cannot proceed."""


@dataclass(frozen=True)
class IdentityExtractionResult:
    document_type: str
    id_number: str | None = None
    full_name: str | None = None
    date_of_birth: str | None = None
    sex: str | None = None
    warnings: list[str] = field(default_factory=list)
    extractor_version: str = EXTRACTOR_VERSION


def _normalize_text(text: str) -> str:
    """Normalize OCR whitespace without merging separate lines."""
    lines = []

    for line in text.splitlines():
        normalized = re.sub(r"\s+", " ", line).strip()

        if normalized:
            lines.append(normalized)

    return "\n".join(lines)


def _extract_labeled_value(
    text: str,
    label_pattern: str,
) -> str | None:
    """
    Extract a value appearing after a recognized field label.

    Only extracts values on the same line to avoid
    accidentally capturing unrelated document fields.
    """
    pattern = (
        rf"(?im)^\s*{label_pattern}"
        rf"\s*[:#\-]?\s+([^\n]+)$"
    )

    match = re.search(pattern, text)

    if not match:
        return None

    return match.group(1).strip()


def _extract_id_number(
    text: str,
    document_type: str,
) -> str | None:
    if document_type == "national_id":
        raw = _extract_labeled_value(text, ID_LABELS)

        if not raw:
            return None

        match = re.fullmatch(r"\d{6,10}", raw.strip())

        return match.group(0) if match else None

    if document_type == "passport":
        raw = _extract_labeled_value(
            text,
            r"(?:PASSPORT\s*(?:NO\.?|NUMBER)|DOCUMENT\s*NUMBER)",
        )

        if not raw:
            return None

        value = raw.strip().upper()

        if re.fullmatch(r"[A-Z0-9]{6,12}", value):
            return value

    return None


def _extract_full_name(text: str) -> str | None:
    raw = _extract_labeled_value(text, NAME_LABELS)

    if not raw:
        return None

    name = raw.strip().upper()

    if not re.fullmatch(r"[A-Z][A-Z '\-]{2,99}", name):
        return None

    return name


def _extract_date_of_birth(text: str) -> str | None:
    raw = _extract_labeled_value(text, DOB_LABELS)

    if not raw:
        return None

    raw = raw.strip()

    formats = (
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%d.%m.%Y",
    )

    for date_format in formats:
        try:
            parsed = datetime.strptime(
                raw,
                date_format,
            ).date()

            if parsed > date.today():
                return None

            if parsed.year < 1900:
                return None

            return parsed.isoformat()

        except ValueError:
            continue

    return None


def _extract_sex(text: str) -> str | None:
    raw = _extract_labeled_value(text, SEX_LABELS)

    if not raw:
        return None

    value = raw.strip().upper()

    mapping = {
        "M": "MALE",
        "MALE": "MALE",
        "F": "FEMALE",
        "FEMALE": "FEMALE",
    }

    return mapping.get(value)


def extract_identity_fields(
    ocr_result: OCRResult,
    document_type: str,
) -> IdentityExtractionResult:
    """
    Extract structured identity fields from OCR output.

    This function does not verify document authenticity.
    """
    if document_type not in SUPPORTED_DOCUMENT_TYPES:
        raise IdentityExtractionError(
            f"Unsupported document type: {document_type}"
        )

    text = _normalize_text(ocr_result.text)

    if not text:
        raise IdentityExtractionError(
            "OCR result contains no readable text."
        )

    id_number = _extract_id_number(
        text,
        document_type,
    )

    full_name = _extract_full_name(text)
    date_of_birth = _extract_date_of_birth(text)
    sex = _extract_sex(text)

    warnings = list(ocr_result.warnings)

    if not id_number:
        warnings.append(
            "Document number could not be extracted."
        )

    if not full_name:
        warnings.append(
            "Full name could not be extracted."
        )

    if not date_of_birth:
        warnings.append(
            "Date of birth could not be extracted."
        )

    if not sex:
        warnings.append(
            "Sex could not be extracted."
        )

    return IdentityExtractionResult(
        document_type=document_type,
        id_number=id_number,
        full_name=full_name,
        date_of_birth=date_of_birth,
        sex=sex,
        warnings=warnings,
    )
