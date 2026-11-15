
import pytest

from app.services.verification.risk_features import (
    RiskFeatures,
)
from app.services.verification.fraud_rules import (
    detect_fraud_indicators,
)


def codes(features):
    return {
        indicator.code
        for indicator in detect_fraud_indicators(features)
    }


def test_clean_document_has_no_indicators():
    features = RiskFeatures("match", "pass")
    assert codes(features) == set()


@pytest.mark.parametrize(
    ("features", "expected"),
    [
        (
            RiskFeatures("mismatch", "pass"),
            "IDENTITY_MISMATCH",
        ),
        (
            RiskFeatures("unknown", "pass"),
            "IDENTITY_UNKNOWN",
        ),
        (
            RiskFeatures("match", "fail"),
            "DOCUMENT_QUALITY_FAILURE",
        ),
        (
            RiskFeatures("match", "review"),
            "DOCUMENT_QUALITY_REVIEW",
        ),
        (
            RiskFeatures(
                "match", "pass",
                missing_required_fields=True,
            ),
            "MISSING_REQUIRED_FIELDS",
        ),
        (
            RiskFeatures(
                "match", "pass",
                conflicting_identity_fields=True,
            ),
            "CONFLICTING_IDENTITY_FIELDS",
        ),
        (
            RiskFeatures(
                "match", "pass",
                duplicate_document_confirmed=True,
            ),
            "DUPLICATE_DOCUMENT",
        ),
        (
            RiskFeatures(
                "match", "pass",
                repeated_failures_confirmed=True,
            ),
            "REPEATED_FAILURES",
        ),
    ],
)
def test_expected_indicator_detected(
    features,
    expected,
):
    assert expected in codes(features)


def test_indicator_codes_are_unique():
    features = RiskFeatures(
        "mismatch",
        "fail",
        missing_required_fields=True,
        duplicate_document_confirmed=True,
    )

    result = detect_fraud_indicators(features)
    result_codes = [item.code for item in result]

    assert len(result_codes) == len(set(result_codes))
