
import uuid
from unittest.mock import MagicMock

import pytest

from app.models.entities import (
    AuditLog,
    CheckStatus,
    FraudAssessment,
    VerificationCheck,
)

from app.services.verification.contracts import (
    DocumentAnalysisResult,
    RiskAssessmentResult,
    RiskLevel,
    VerificationOutcome,
)

from app.services.verification.persistence import (
    VerificationPersistenceError,
    save_document_analysis,
    save_risk_assessment,
)


def test_save_document_analysis():
    db = MagicMock()
    agent_id = uuid.uuid4()
    document_id = uuid.uuid4()

    result = DocumentAnalysisResult(
        document_id=document_id,
        document_type="national_id_front",
        outcome=VerificationOutcome.NEEDS_REVIEW,
        extracted_fields={
            "national_id": "SENSITIVE_TEST_VALUE"
        },
        analyzer_version="rules-v1",
    )

    check = save_document_analysis(
        db=db,
        agent_id=agent_id,
        result=result,
    )

    assert isinstance(check, VerificationCheck)
    assert check.agent_id == agent_id
    assert check.status == CheckStatus.NEEDS_REVIEW

    assert check.result_data["document_id"] == str(
        document_id
    )

    # Sensitive extracted fields must not be persisted.
    assert "extracted_fields" not in check.result_data
    assert "SENSITIVE_TEST_VALUE" not in str(
        check.result_data
    )

    assert db.add.call_count == 2

    added_objects = [
        call.args[0] for call in db.add.call_args_list
    ]

    assert any(
        isinstance(obj, AuditLog)
        for obj in added_objects
    )

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(check)


def test_save_risk_assessment():
    db = MagicMock()
    agent_id = uuid.uuid4()

    result = RiskAssessmentResult(
        agent_id=agent_id,
        risk_score=42,
        risk_level=RiskLevel.MEDIUM,
        model_version="rules-v1",
    )

    assessment = save_risk_assessment(
        db=db,
        result=result,
    )

    assert isinstance(assessment, FraudAssessment)
    assert assessment.agent_id == agent_id
    assert assessment.risk_score == 42
    assert assessment.risk_level == "medium"

    assert db.add.call_count == 2
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(assessment)


def test_document_analysis_rollback_on_failure():
    db = MagicMock()
    db.commit.side_effect = RuntimeError(
        "Simulated database failure"
    )

    result = DocumentAnalysisResult(
        document_id=uuid.uuid4(),
        document_type="passport",
        outcome=VerificationOutcome.FAIL,
        analyzer_version="rules-v1",
    )

    with pytest.raises(VerificationPersistenceError):
        save_document_analysis(
            db=db,
            agent_id=uuid.uuid4(),
            result=result,
        )

    db.rollback.assert_called_once()


def test_risk_assessment_rollback_on_failure():
    db = MagicMock()
    db.commit.side_effect = RuntimeError(
        "Simulated database failure"
    )

    result = RiskAssessmentResult(
        agent_id=uuid.uuid4(),
        risk_score=85,
        risk_level=RiskLevel.HIGH,
        model_version="rules-v1",
    )

    with pytest.raises(VerificationPersistenceError):
        save_risk_assessment(
            db=db,
            result=result,
        )

    db.rollback.assert_called_once()
