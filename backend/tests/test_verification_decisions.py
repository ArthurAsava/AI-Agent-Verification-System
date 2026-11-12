
import pytest

from app.services.verification.decision_contracts import (
    CaseStatus,
    Recommendation,
)
from app.services.verification.state_machine import (
    InvalidVerificationTransition,
    validate_transition,
)
from app.services.verification.risk_features import (
    RiskFeatures,
)
from app.services.verification.risk_engine import (
    assess_risk,
)
from app.services.verification.recommendation import (
    build_recommendation,
)


def test_clean_case_recommends_pass():
    risk = assess_risk(
        RiskFeatures("match", "pass")
    )

    result = build_recommendation(risk, True)

    assert (
        result.recommendation
        == Recommendation.RECOMMEND_PASS
    )
    assert result.requires_human_review


def test_uncertain_case_requires_review():
    risk = assess_risk(
        RiskFeatures("unknown", "pass")
    )

    result = build_recommendation(risk, False)

    assert (
        result.recommendation
        == Recommendation.MANUAL_REVIEW
    )


def test_high_risk_escalates():
    risk = assess_risk(
        RiskFeatures(
            "mismatch",
            "fail",
            missing_required_fields=True,
        )
    )

    result = build_recommendation(risk, False)

    assert (
        result.recommendation
        == Recommendation.ESCALATE
    )


def test_valid_transition():
    validate_transition(
        CaseStatus.ANALYZING,
        CaseStatus.AWAITING_REVIEW,
    )


def test_automatic_approval_transition_blocked():
    with pytest.raises(
        InvalidVerificationTransition
    ):
        validate_transition(
            CaseStatus.ANALYZING,
            CaseStatus.APPROVED,
        )


def test_finalized_case_cannot_reopen():
    with pytest.raises(
        InvalidVerificationTransition
    ):
        validate_transition(
            CaseStatus.APPROVED,
            CaseStatus.ANALYZING,
        )
