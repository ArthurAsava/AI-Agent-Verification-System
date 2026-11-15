
from uuid import uuid4

from app.services.verification.contracts import RiskLevel
from app.services.verification.risk_features import RiskFeatures
from app.services.verification.risk_engine import assess_risk
from app.services.verification.risk_contract_adapter import (
    to_risk_assessment_contract,
)


def test_clean_assessment():
    result = to_risk_assessment_contract(
        agent_id=uuid4(),
        result=assess_risk(RiskFeatures("match", "pass")),
    )
    assert result.risk_score == 0
    assert result.risk_level == RiskLevel.LOW
    assert result.indicators == []


def test_mismatch_assessment():
    result = to_risk_assessment_contract(
        agent_id=uuid4(),
        result=assess_risk(RiskFeatures("mismatch", "pass")),
    )
    assert result.risk_score == 45
    assert result.risk_level == RiskLevel.MEDIUM
    assert result.indicators[0].code == "IDENTITY_MISMATCH"


def test_critical_assessment_is_preserved():
    result = to_risk_assessment_contract(
        agent_id=uuid4(),
        result=assess_risk(
            RiskFeatures(
                "mismatch",
                "fail",
                missing_required_fields=True,
            )
        ),
    )
    assert result.risk_score == 80
    assert result.risk_level == RiskLevel.CRITICAL
