
from __future__ import annotations

from dataclasses import dataclass

from app.services.verification.risk_features import (
    RiskFeatures,
)


@dataclass(frozen=True)
class DetectedIndicator:
    code: str
    weight: int
    explanation: str


def detect_fraud_indicators(
    features: RiskFeatures,
) -> tuple[DetectedIndicator, ...]:
    indicators: list[DetectedIndicator] = []

    def add(
        code: str,
        weight: int,
        explanation: str,
    ) -> None:
        indicators.append(
            DetectedIndicator(
                code=code,
                weight=weight,
                explanation=explanation,
            )
        )

    if features.identity_match == "mismatch":
        add(
            "IDENTITY_MISMATCH",
            45,
            "Document identity conflicts with "
            "registered agent information.",
        )

    elif features.identity_match == "unknown":
        add(
            "IDENTITY_UNKNOWN",
            15,
            "Identity comparison is inconclusive.",
        )

    if features.document_quality == "fail":
        add(
            "DOCUMENT_QUALITY_FAILURE",
            20,
            "Document quality checks failed.",
        )

    elif features.document_quality == "review":
        add(
            "DOCUMENT_QUALITY_REVIEW",
            10,
            "Document quality requires review.",
        )

    elif features.document_quality == "unknown":
        add(
            "DOCUMENT_QUALITY_UNKNOWN",
            10,
            "Document quality could not be established.",
        )

    if features.missing_required_fields:
        add(
            "MISSING_REQUIRED_FIELDS",
            15,
            "Required identity fields are missing.",
        )

    if features.conflicting_identity_fields:
        add(
            "CONFLICTING_IDENTITY_FIELDS",
            30,
            "Conflicting identity fields were detected.",
        )

    if features.duplicate_document_confirmed:
        add(
            "DUPLICATE_DOCUMENT",
            45,
            "The same document checksum is associated "
            "with another agent.",
        )

    if features.repeated_failures_confirmed:
        add(
            "REPEATED_FAILURES",
            20,
            "Relevant repeated verification failures "
            "were detected.",
        )

    if features.unusual_verification_frequency:
        add(
            "UNUSUAL_VERIFICATION_FREQUENCY",
            20,
            "Verification attempts exceeded the review "
            "threshold within the configured time window.",
        )

    if features.provider_kyc_declined:
        add(
            "PROVIDER_KYC_DECLINED",
            35,
            "A trusted KYC provider reported a declined outcome.",
        )

    if features.provider_liveness_failed:
        add(
            "PROVIDER_LIVENESS_FAILURE",
            30,
            "A trusted KYC provider reported a failed liveness check.",
        )

    if features.provider_identity_check_failed:
        add(
            "PROVIDER_IDENTITY_CHECK_FAILURE",
            30,
            "A trusted KYC provider reported a failed identity check.",
        )

    return tuple(indicators)
