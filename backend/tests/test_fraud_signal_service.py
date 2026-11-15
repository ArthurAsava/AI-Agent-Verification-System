from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.services.verification.fraud_signal_service import (
    REPEATED_FAILURE_THRESHOLD,
    VERIFICATION_FREQUENCY_THRESHOLD,
    FraudSignalEvidence,
    assessment_key_for,
    collect_trusted_fraud_signal_evidence,
)
from app.services.verification.risk_features import RiskFeatures


def test_evidence_enriches_features_and_uses_review_thresholds():
    evidence = FraudSignalEvidence(
        duplicate_document_count=1,
        historical_failed_check_count=REPEATED_FAILURE_THRESHOLD,
        recent_verification_case_count=(
            VERIFICATION_FREQUENCY_THRESHOLD
        ),
        provider_kyc_declined=True,
        provider_liveness_failed=True,
        provider_identity_check_failed=True,
    )

    features = evidence.apply_to(RiskFeatures("match", "pass"))

    assert features.duplicate_document_confirmed is True
    assert features.repeated_failures_confirmed is True
    assert features.unusual_verification_frequency is True
    assert features.provider_kyc_declined is True
    assert features.provider_liveness_failed is True
    assert features.provider_identity_check_failed is True
    assert evidence.indicator_evidence()["DUPLICATE_DOCUMENT"] == {
        "matched_other_agent_documents": 1
    }


def test_below_threshold_counts_do_not_become_flags():
    evidence = FraudSignalEvidence(
        historical_failed_check_count=(
            REPEATED_FAILURE_THRESHOLD - 1
        ),
        recent_verification_case_count=(
            VERIFICATION_FREQUENCY_THRESHOLD - 1
        ),
    )

    features = evidence.apply_to(RiskFeatures("match", "pass"))

    assert features.repeated_failures_confirmed is False
    assert features.unusual_verification_frequency is False
    assert evidence.indicator_evidence() == {}


def test_collection_uses_counts_and_minimized_didit_summary_only():
    agent_id = uuid4()
    document_id = uuid4()
    check_id = uuid4()
    results = [
        SimpleNamespace(scalar_one_or_none=lambda: "a" * 64),
        SimpleNamespace(scalar_one=lambda: 2),
        SimpleNamespace(scalar_one=lambda: 3),
        SimpleNamespace(scalar_one=lambda: 4),
        SimpleNamespace(
            scalar_one_or_none=lambda: {
                "didit": {
                    "kyc": {
                        "status": "declined",
                        "actions": {
                            "liveness": "approved, failed",
                            "id_verification": "rejected",
                        },
                    }
                }
            }
        ),
    ]

    class FakeSession:
        def execute(self, _statement):
            return results.pop(0)

    evidence = collect_trusted_fraud_signal_evidence(
        db=FakeSession(),
        agent_id=agent_id,
        document_id=document_id,
        current_check_id=check_id,
        now=datetime(2026, 11, 15, tzinfo=timezone.utc),
    )

    assert evidence.duplicate_document_count == 2
    assert evidence.historical_failed_check_count == 3
    assert evidence.recent_verification_case_count == 4
    assert evidence.provider_kyc_declined is True
    assert evidence.provider_liveness_failed is True
    assert evidence.provider_identity_check_failed is True


def test_assessment_key_is_stable_and_does_not_contain_identifiers():
    agent_id = uuid4()
    document_id = uuid4()
    case_id = uuid4()
    features = RiskFeatures("match", "pass")

    first = assessment_key_for(
        agent_id=agent_id,
        document_id=document_id,
        case_id=case_id,
        features=features,
        scoring_version="risk-rules-v2",
    )
    second = assessment_key_for(
        agent_id=agent_id,
        document_id=document_id,
        case_id=case_id,
        features=features,
        scoring_version="risk-rules-v2",
    )

    assert first == second
    assert len(first) == 64
    assert str(agent_id) not in first
    assert str(document_id) not in first
    assert str(case_id) not in first
