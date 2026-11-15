
from __future__ import annotations

from app.services.verification.risk_features import (
    RiskFeatures,
)
from app.services.verification.risk_engine import (
    assess_risk,
)


CASES = [
    (
        "Clean synthetic case",
        RiskFeatures("match", "pass"),
        "low",
    ),
    (
        "Unknown identity",
        RiskFeatures("unknown", "pass"),
        "low",
    ),
    (
        "Identity mismatch",
        RiskFeatures("mismatch", "pass"),
        "medium",
    ),
    (
        "Poor document quality",
        RiskFeatures("match", "fail"),
        "low",
    ),
    (
        "Missing fields",
        RiskFeatures(
            "match",
            "pass",
            missing_required_fields=True,
        ),
        "low",
    ),
    (
        "Identity and quality problems",
        RiskFeatures("mismatch", "fail"),
        "high",
    ),
    (
        "Confirmed duplicate document",
        RiskFeatures(
            "match",
            "pass",
            duplicate_document_confirmed=True,
        ),
        "medium",
    ),
    (
        "Repeated failures",
        RiskFeatures(
            "match",
            "pass",
            repeated_failures_confirmed=True,
        ),
        "low",
    ),
    (
        "Multiple strong indicators",
        RiskFeatures(
            "mismatch",
            "fail",
            missing_required_fields=True,
            duplicate_document_confirmed=True,
        ),
        "critical",
    ),
]


def main():
    passed = 0

    print("\n=== PHASE 8C RISK EVALUATION ===")

    for name, features, expected in CASES:
        result = assess_risk(features)

        correct = result.risk.level == expected

        if correct:
            passed += 1

        print(f"\nScenario: {name}")
        print(f"Score: {result.risk.score}")
        print(f"Level: {result.risk.level}")
        print(f"Review: {result.requires_review}")
        print(
            "Indicators:",
            [item.code for item in result.indicators],
        )
        print(
            "Result:",
            "PASS" if correct else "FAIL",
        )

    print(
        f"\nEvaluation: {passed}/{len(CASES)} passed"
    )

    if passed != len(CASES):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
