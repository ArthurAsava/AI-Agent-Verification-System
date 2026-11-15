
from __future__ import annotations

from app.services.verification.pipeline import (
    VerificationPipelineResult,
)
from app.services.verification.risk_features import (
    RiskFeatures,
)


def extract_risk_features_from_analysis(
    result: VerificationPipelineResult,
) -> RiskFeatures:
    if not isinstance(result, VerificationPipelineResult):
        raise TypeError("Expected VerificationPipelineResult")

    match = getattr(
        result.match_status,
        "value",
        result.match_status,
    )

    match = str(match).lower()

    if match not in {"match", "mismatch", "unknown"}:
        match = "unknown"

    quality = str(result.quality_status).lower()

    if quality == "needs_review":
        quality = "review"

    if quality not in {"pass", "review", "fail", "unknown"}:
        quality = "unknown"

    detected = result.analysis.extracted_fields.get(
        "identity_fields_detected",
        {},
    )

    if not isinstance(detected, dict):
        raise ValueError("Invalid identity evidence")

    missing_fields = (
        detected.get("full_name") is not True
        or detected.get("document_number") is not True
    )

    return RiskFeatures(
        identity_match=match,
        document_quality=quality,
        missing_required_fields=missing_fields,
        conflicting_identity_fields=False,
        duplicate_document_confirmed=False,
        repeated_failures_confirmed=False,
    )
