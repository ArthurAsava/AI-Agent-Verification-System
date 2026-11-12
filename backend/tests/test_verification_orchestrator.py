
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.services.verification import (
    verification_orchestrator as module,
)


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
