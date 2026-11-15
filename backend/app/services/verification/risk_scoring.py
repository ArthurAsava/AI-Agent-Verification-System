
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.verification.fraud_rules import (
    DetectedIndicator,
)


RiskBand = Literal[
    "low",
    "medium",
    "high",
    "critical",
]

SCORING_VERSION = "risk-rules-v1"


@dataclass(frozen=True)
class ScoredRisk:
    score: int
    level: RiskBand
    scoring_version: str


def classify_risk(score: int) -> RiskBand:
    if type(score) is not int or not 0 <= score <= 100:
        raise ValueError(
            "Risk score must be an integer from 0 to 100."
        )

    if score < 25:
        return "low"

    if score < 50:
        return "medium"

    if score < 75:
        return "high"

    return "critical"


def calculate_risk_score(
    indicators: tuple[DetectedIndicator, ...],
) -> ScoredRisk:
    if not isinstance(indicators, tuple):
        raise ValueError(
            "Indicators must be an immutable tuple."
        )

    seen_codes: set[str] = set()
    total = 0

    for indicator in indicators:
        if not isinstance(indicator, DetectedIndicator):
            raise ValueError("Invalid risk indicator.")

        if indicator.code in seen_codes:
            raise ValueError(
                "Duplicate risk indicator code."
            )

        if (
            type(indicator.weight) is not int
            or indicator.weight < 0
        ):
            raise ValueError(
                "Indicator weight must be nonnegative."
            )

        seen_codes.add(indicator.code)
        total += indicator.weight

    score = min(100, total)

    return ScoredRisk(
        score=score,
        level=classify_risk(score),
        scoring_version=SCORING_VERSION,
    )
