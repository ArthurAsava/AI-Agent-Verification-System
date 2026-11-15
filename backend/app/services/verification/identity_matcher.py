
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum

from app.services.verification.identity_extractor import (
    IdentityExtractionResult,
)


MATCHER_VERSION = "identity-matcher-v1"


class MatchStatus(str, Enum):
    MATCH = "match"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AgentIdentityReference:
    first_name: str | None
    last_name: str | None
    document_number: str | None = None
    date_of_birth: str | None = None


@dataclass(frozen=True)
class FieldMatchResult:
    field_name: str
    status: MatchStatus
    reason: str


@dataclass(frozen=True)
class IdentityMatchResult:
    overall_status: MatchStatus
    fields: list[FieldMatchResult]
    warnings: list[str] = field(default_factory=list)
    matcher_version: str = MATCHER_VERSION


def _normalize_name(value: str) -> str:
    """
    Normalize case, Unicode and whitespace.

    Does not use fuzzy matching.
    """
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.casefold()
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized.strip()


def _compare_exact(
    field_name: str,
    reference: str | None,
    extracted: str | None,
) -> FieldMatchResult:
    if not reference or not extracted:
        return FieldMatchResult(
            field_name=field_name,
            status=MatchStatus.UNKNOWN,
            reason="Reference or extracted value is unavailable.",
        )

    if reference == extracted:
        return FieldMatchResult(
            field_name=field_name,
            status=MatchStatus.MATCH,
            reason="Values match exactly.",
        )

    return FieldMatchResult(
        field_name=field_name,
        status=MatchStatus.MISMATCH,
        reason="Values differ.",
    )


def _compare_name(
    reference: AgentIdentityReference,
    extracted_full_name: str | None,
) -> FieldMatchResult:
    if (
        not reference.first_name
        or not reference.last_name
        or not extracted_full_name
    ):
        return FieldMatchResult(
            field_name="full_name",
            status=MatchStatus.UNKNOWN,
            reason="Required name information is unavailable.",
        )

    first_name = _normalize_name(reference.first_name)
    last_name = _normalize_name(reference.last_name)
    document_name = _normalize_name(extracted_full_name)

    tokens = document_name.split()

    if (
        len(tokens) >= 2
        and tokens[0] == first_name
        and tokens[-1] == last_name
    ):
        return FieldMatchResult(
            field_name="full_name",
            status=MatchStatus.MATCH,
            reason="First and last names match the document.",
        )

    return FieldMatchResult(
        field_name="full_name",
        status=MatchStatus.MISMATCH,
        reason="Registered names do not match document names.",
    )


def match_agent_identity(
    reference: AgentIdentityReference,
    extracted: IdentityExtractionResult,
) -> IdentityMatchResult:
    """
    Compare extracted document identity against agent data.

    Does not approve, reject or modify an agent.
    """

    name_result = _compare_name(
        reference,
        extracted.full_name,
    )

    document_result = _compare_exact(
        "document_number",
        (
            reference.document_number.strip().upper()
            if reference.document_number
            else None
        ),
        (
            extracted.id_number.strip().upper()
            if extracted.id_number
            else None
        ),
    )

    dob_result = _compare_exact(
        "date_of_birth",
        reference.date_of_birth,
        extracted.date_of_birth,
    )

    fields = [
        name_result,
        document_result,
        dob_result,
    ]

    statuses = [item.status for item in fields]

    if MatchStatus.MISMATCH in statuses:
        overall = MatchStatus.MISMATCH

    elif all(status == MatchStatus.MATCH for status in statuses):
        overall = MatchStatus.MATCH

    else:
        overall = MatchStatus.UNKNOWN

    warnings = list(extracted.warnings)

    for item in fields:
        if item.status == MatchStatus.MISMATCH:
            warnings.append(
                f"{item.field_name} requires manual review."
            )

    return IdentityMatchResult(
        overall_status=overall,
        fields=fields,
        warnings=warnings,
    )
