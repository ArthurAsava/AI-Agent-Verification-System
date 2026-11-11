
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


MatchSignal = Literal[
    "match",
    "mismatch",
    "unknown",
]

QualitySignal = Literal[
    "pass",
    "review",
    "fail",
    "unknown",
]


@dataclass(frozen=True)
class RiskFeatures:
    """
    Normalized, non-PII signals derived from
    trusted verification results.

    These are analysis signals, not proof of fraud.
    """

    identity_match: MatchSignal
    document_quality: QualitySignal

    missing_required_fields: bool = False
    conflicting_identity_fields: bool = False

    # Optional trusted database-derived evidence.
    duplicate_document_confirmed: bool = False
    repeated_failures_confirmed: bool = False

    def __post_init__(self) -> None:
        if self.identity_match not in (
            "match", "mismatch", "unknown"
        ):
            raise ValueError(
                "Invalid identity match signal."
            )

        if self.document_quality not in (
            "pass", "review", "fail", "unknown"
        ):
            raise ValueError(
                "Invalid document quality signal."
            )

        for name in (
            "missing_required_fields",
            "conflicting_identity_fields",
            "duplicate_document_confirmed",
            "repeated_failures_confirmed",
        ):
            if type(getattr(self, name)) is not bool:
                raise ValueError(
                    f"{name} must be boolean."
                )
