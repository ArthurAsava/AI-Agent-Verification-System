
import pytest

from app.services.verification.fraud_rules import (
    DetectedIndicator,
)
from app.services.verification.risk_scoring import (
    calculate_risk_score,
    classify_risk,
)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0, "low"),
        (24, "low"),
        (25, "medium"),
        (49, "medium"),
        (50, "high"),
        (74, "high"),
        (75, "critical"),
        (100, "critical"),
    ],
)
def test_risk_boundaries(score, expected):
    assert classify_risk(score) == expected


@pytest.mark.parametrize(
    "score",
    [-1, 101, 25.5, True],
)
def test_invalid_score_rejected(score):
    with pytest.raises(ValueError):
        classify_risk(score)


def test_empty_indicators_produce_zero():
    result = calculate_risk_score(())
    assert result.score == 0
    assert result.level == "low"


def test_score_is_capped_at_100():
    indicators = (
        DetectedIndicator("A", 70, "Synthetic A"),
        DetectedIndicator("B", 70, "Synthetic B"),
    )

    result = calculate_risk_score(indicators)
    assert result.score == 100
    assert result.level == "critical"


def test_duplicate_codes_rejected():
    indicators = (
        DetectedIndicator("A", 10, "First"),
        DetectedIndicator("A", 10, "Second"),
    )

    with pytest.raises(ValueError):
        calculate_risk_score(indicators)
