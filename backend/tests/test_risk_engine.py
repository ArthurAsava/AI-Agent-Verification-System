
from app.services.verification.risk_features import (
    RiskFeatures,
)
from app.services.verification.risk_engine import (
    assess_risk,
)


def test_clean_synthetic_case():
    result = assess_risk(
        RiskFeatures("match", "pass")
    )

    assert result.risk.score == 0
    assert result.risk.level == "low"
    assert result.requires_review is False
    assert result.indicators == ()


def test_identity_mismatch():
    result = assess_risk(
        RiskFeatures("mismatch", "pass")
    )

    assert result.risk.score == 45
    assert result.risk.level == "medium"
    assert result.requires_review is True


def test_unknown_identity_requires_review():
    result = assess_risk(
        RiskFeatures("unknown", "pass")
    )

    assert result.risk.score == 15
    assert result.requires_review is True


def test_multiple_signals():
    result = assess_risk(
        RiskFeatures(
            identity_match="mismatch",
            document_quality="fail",
            missing_required_fields=True,
        )
    )

    assert result.risk.score == 80
    assert result.risk.level == "critical"
    assert result.requires_review is True


def test_same_features_same_result():
    features = RiskFeatures(
        "mismatch",
        "review",
        duplicate_document_confirmed=True,
    )

    assert assess_risk(features) == assess_risk(features)


def test_optional_database_signals():
    result = assess_risk(
        RiskFeatures(
            "match",
            "pass",
            duplicate_document_confirmed=True,
            repeated_failures_confirmed=True,
        )
    )

    assert result.risk.score == 55
    assert result.risk.level == "high"
    assert result.requires_review is True
