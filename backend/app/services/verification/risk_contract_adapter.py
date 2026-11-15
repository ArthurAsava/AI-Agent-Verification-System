
from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from app.services.verification.contracts import (
    FraudIndicator,
    RiskAssessmentResult,
    RiskLevel,
)
from app.services.verification.risk_engine import (
    RiskEngineResult,
)


def to_risk_assessment_contract(
    *,
    agent_id: UUID,
    result: RiskEngineResult,
    indicator_evidence: Mapping[str, Mapping[str, int]] | None = None,
) -> RiskAssessmentResult:

    if not isinstance(result, RiskEngineResult):
        raise TypeError("Expected RiskEngineResult")

    level_map = {
        "low": RiskLevel.LOW,
        "medium": RiskLevel.MEDIUM,
        "high": RiskLevel.HIGH,
        "critical": RiskLevel.CRITICAL,
    }

    level = level_map.get(result.risk.level)

    if level is None:
        raise ValueError("Unsupported risk level")

    indicators = []

    for indicator in result.indicators:
        if indicator.weight >= 40:
            severity = RiskLevel.HIGH
        elif indicator.weight >= 25:
            severity = RiskLevel.MEDIUM
        else:
            severity = RiskLevel.LOW

        evidence = {"weight": indicator.weight}
        if indicator_evidence and indicator.code in indicator_evidence:
            evidence.update(indicator_evidence[indicator.code])

        indicators.append(
            FraudIndicator(
                code=indicator.code,
                description=indicator.explanation,
                severity=severity,
                evidence=evidence,
            )
        )

    return RiskAssessmentResult(
        agent_id=agent_id,
        risk_score=result.risk.score,
        risk_level=level,
        model_version=result.risk.scoring_version,
        indicators=indicators,
        requires_review=result.requires_review,
    )
