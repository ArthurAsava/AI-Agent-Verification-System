
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.services.verification import (
    verification_orchestrator as module,
)
from app.services.verification.contracts import VerificationOutcome


def test_risk_failure_rolls_back(monkeypatch):
    user_id = uuid4()
    agent_id = uuid4()
    document_id = uuid4()

    agent = SimpleNamespace(id=agent_id)
    document = SimpleNamespace(
        id=document_id,
        agent_id=agent_id,
        storage_path="agent/document.png",
        storage_bucket="kyc-documents",
        sha256_checksum="synthetic-checksum",
    )

    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.side_effect = [
        agent,
        document,
    ]

    context = MagicMock()
    context.__enter__.return_value = db
    context.__exit__.return_value = False

    monkeypatch.setattr(
        module,
        "SessionLocal",
        lambda: context,
    )

    workflow_result = SimpleNamespace(
        check_id=uuid4(),
        pipeline_result=object(),
    )

    def fake_workflow(**kwargs):
        assert kwargs["commit"] is False
        return workflow_result

    monkeypatch.setattr(
        module,
        "run_document_verification",
        fake_workflow,
    )

    def fail_adapter(*args):
        raise RuntimeError("Simulated risk failure")

    monkeypatch.setattr(
        module,
        "extract_risk_features_from_analysis",
        fail_adapter,
    )

    with pytest.raises(RuntimeError, match="Simulated risk"):
        module._run_verification_sync(
            user_id=user_id,
            document_id=document_id,
            document_bytes=b"synthetic",
            expected_storage_path="agent/document.png",
            expected_storage_bucket="kyc-documents",
            expected_checksum="synthetic-checksum",
        )

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_completed_analysis_moves_case_to_human_review(monkeypatch):
    user_id = uuid4()
    agent_id = uuid4()
    document_id = uuid4()
    case_id = uuid4()

    agent = SimpleNamespace(
        id=agent_id,
        status=None,
    )
    document = SimpleNamespace(
        id=document_id,
        agent_id=agent_id,
        storage_path="agent/document.png",
        storage_bucket="kyc-documents",
        sha256_checksum="synthetic-checksum",
    )
    case = SimpleNamespace(
        id=case_id,
        agent_id=agent_id,
        status="analyzing",
        recommendation=None,
        risk_score=None,
        risk_level=None,
        scoring_version=None,
        version=0,
        updated_at=None,
    )

    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.side_effect = [
        agent,
        document,
        case,
    ]
    context = MagicMock()
    context.__enter__.return_value = db
    context.__exit__.return_value = False
    monkeypatch.setattr(module, "SessionLocal", lambda: context)

    workflow = SimpleNamespace(
        check_id=uuid4(),
        pipeline_result=SimpleNamespace(
            analysis=SimpleNamespace(
                outcome=VerificationOutcome.PASS,
            ),
            document_sex="MALE",
        ),
    )
    risk = SimpleNamespace(
        risk=SimpleNamespace(
            score=15,
            level="low",
            scoring_version="risk-rules-v1",
        ),
        indicators=(),
    )
    recommendation = SimpleNamespace(
        recommendation=SimpleNamespace(value="recommend_pass"),
    )

    monkeypatch.setattr(
        module,
        "run_document_verification",
        lambda **_: workflow,
    )
    monkeypatch.setattr(
        module,
        "extract_risk_features_from_analysis",
        lambda _: object(),
    )
    evidence = SimpleNamespace(
        apply_to=lambda _: object(),
        indicator_evidence=lambda: {},
    )
    monkeypatch.setattr(
        module,
        "collect_trusted_fraud_signal_evidence",
        lambda **_: evidence,
    )
    monkeypatch.setattr(
        module,
        "assessment_key_for",
        lambda **_: "a" * 64,
    )
    monkeypatch.setattr(module, "assess_risk", lambda _: risk)
    monkeypatch.setattr(
        module,
        "to_risk_assessment_contract",
        lambda **_: object(),
    )
    monkeypatch.setattr(
        module,
        "save_risk_assessment",
        lambda **_: SimpleNamespace(id=uuid4()),
    )
    monkeypatch.setattr(
        module,
        "build_recommendation",
        lambda *_, **__: recommendation,
    )

    result = module._run_verification_sync(
        user_id=user_id,
        document_id=document_id,
        document_bytes=b"synthetic",
        expected_storage_path="agent/document.png",
        expected_storage_bucket="kyc-documents",
        expected_checksum="synthetic-checksum",
        case_id=case_id,
    )

    assert result.case_id == case_id
    assert case.status == "awaiting_review"
    assert case.recommendation == "recommend_pass"
    assert case.risk_score == 15
    assert case.risk_level == "low"
    assert case.scoring_version == "risk-rules-v1"
    assert case.avatar_variant.value == "male"
    assert case.version == 1
    assert agent.status.value == "under_review"
    db.commit.assert_called_once()
