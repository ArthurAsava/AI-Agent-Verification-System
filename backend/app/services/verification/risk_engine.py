
from __future__ import annotations

from dataclasses import dataclass

from app.services.verification.fraud_rules import (
    DetectedIndicator,
    detect_fraud_indicators,
)
from app.services.verification.risk_features import (
    RiskFeatures,
)
from app.services.verification.risk_scoring import (
    ScoredRisk,
    calculate_risk_score,
)


@dataclass(frozen=True)
class RiskEngineResult:
    features: RiskFeatures
    indicators: tuple[DetectedIndicator, ...]
    risk: ScoredRisk
    requires_review: bool


def assess_risk(
    features: RiskFeatures,
) -> RiskEngineResult:
    if not isinstance(features, RiskFeatures):
        raise ValueError(
            "Expected validated RiskFeatures."
        )

    indicators = detect_fraud_indicators(features)

    scored = calculate_risk_score(indicators)

    # Unknown or incomplete identity evidence
    # requires review even when the numeric score
    # is below the medium-risk threshold.
    requires_review = (
        scored.level != "low"
        or features.identity_match != "match"
        or features.document_quality != "pass"
        or features.missing_required_fields
        or features.conflicting_identity_fields
        or features.duplicate_document_confirmed
        or features.repeated_failures_confirmed
    )

    return RiskEngineResult(
        features=features,
        indicators=indicators,
        risk=scored,
        requires_review=requires_review,
    )
