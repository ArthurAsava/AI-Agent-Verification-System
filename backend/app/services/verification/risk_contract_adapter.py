
from __future__ import annotations

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
) -> RiskAssessmentResult:

    if not isinstance(result, RiskEngineResult):
        raise TypeError("Expected RiskEngineResult")

    level_map = {
        "low": RiskLevel.LOW,
        "medium": RiskLevel.MEDIUM,
        "high": RiskLevel.HIGH,
        "critical": RiskLevel.HIGH,
    }

    level = level_map.get(result.risk.level)

    if level is None:
        raise ValueError("Unsupported risk level")

    indicators = []

    for indicator in result.indicators:
        if indicator.weight >= 50:
            severity = RiskLevel.HIGH
        elif indicator.weight >= 25:
            severity = RiskLevel.MEDIUM
        else:
            severity = RiskLevel.LOW

        indicators.append(
            FraudIndicator(
                code=indicator.code,
                description=indicator.explanation,
                severity=severity,
                evidence={"weight": indicator.weight},
            )
        )

    return RiskAssessmentResult(
        agent_id=agent_id,
        risk_score=result.risk.score,
        risk_level=level,
        model_version=result.risk.scoring_version,
        indicators=indicators,
    )
