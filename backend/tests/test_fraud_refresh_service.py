from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.services.verification import fraud_refresh_service as module
from app.services.verification.fraud_signal_service import FraudSignalEvidence


def test_saved_rule_codes_reconstruct_only_safe_baseline_features():
    assessment = SimpleNamespace(
        signals=[
            {"code": "IDENTITY_UNKNOWN"},
            {"code": "DOCUMENT_QUALITY_REVIEW"},
            {"code": "MISSING_REQUIRED_FIELDS"},
        ]
    )

    features = module.base_features_from_assessment(assessment)

    assert features.identity_match == "unknown"
    assert features.document_quality == "review"
    assert features.missing_required_fields is True
    assert features.duplicate_document_confirmed is False
    assert features.provider_kyc_declined is False


def test_provider_refresh_updates_open_case_but_never_agent_state(monkeypatch):
    agent_id = uuid4()
    case_id = uuid4()
    document_id = uuid4()
    previous = SimpleNamespace(
        id=uuid4(),
        agent_id=agent_id,
        verification_case_id=case_id,
        signals=[],
    )
    case = SimpleNamespace(
        id=case_id,
        agent_id=agent_id,
        document_id=document_id,
        status="awaiting_review",
        recommendation="recommend_pass",
        risk_score=0,
        risk_level="low",
        scoring_version="risk-rules-v2",
        version=2,
        updated_at=None,
    )
    previous_result = MagicMock()
    previous_result.scalar_one_or_none.return_value = previous
    case_result = MagicMock()
    case_result.scalar_one_or_none.return_value = case
    db = MagicMock()
    db.execute.side_effect = [previous_result, case_result]

    monkeypatch.setattr(
        module,
        "collect_trusted_fraud_signal_evidence",
        lambda **_: FraudSignalEvidence(provider_kyc_declined=True),
    )
    refreshed = SimpleNamespace(id=uuid4())
    monkeypatch.setattr(
        module,
        "save_risk_assessment",
        lambda **kwargs: refreshed,
    )

    result = module.refresh_fraud_assessment_after_provider_sync(
        db=db,
        agent_id=agent_id,
    )

    assert result is refreshed
    assert case.status == "awaiting_review"
    assert case.risk_score == 35
    assert case.risk_level == "medium"
    assert case.recommendation == "manual_review"
    assert case.version == 3
    db.add.assert_called_once()
    db.flush.assert_called_once()


def test_provider_refresh_has_no_effect_without_phase_ten_case():
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = MagicMock()
    db.execute.return_value = result

    assert module.refresh_fraud_assessment_after_provider_sync(
        db=db,
        agent_id=uuid4(),
    ) is None
    db.add.assert_not_called()
