
import pytest

from app.services.verification.risk_features import (
    RiskFeatures,
)


def test_valid_features():
    features = RiskFeatures(
        identity_match="match",
        document_quality="pass",
    )

    assert features.identity_match == "match"
    assert features.document_quality == "pass"


@pytest.mark.parametrize(
    "value",
    ["invalid", "", None],
)
def test_invalid_match_rejected(value):
    with pytest.raises(ValueError):
        RiskFeatures(
            identity_match=value,
            document_quality="pass",
        )


def test_invalid_quality_rejected():
    with pytest.raises(ValueError):
        RiskFeatures(
            identity_match="match",
            document_quality="invalid",
        )


def test_non_boolean_evidence_rejected():
    with pytest.raises(ValueError):
        RiskFeatures(
            identity_match="match",
            document_quality="pass",
            duplicate_document_confirmed="yes",
        )
