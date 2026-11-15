
import uuid
from types import SimpleNamespace
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
    VerificationIntegrityError,
    VerificationPersistenceError,
    save_document_analysis,
    save_risk_assessment,
)


def make_document_result(
    document_id=None,
    document_type="national_id_front",
):
    return DocumentAnalysisResult(
        document_id=document_id or uuid.uuid4(),
        document_type=document_type,
        outcome=VerificationOutcome.NEEDS_REVIEW,
        extracted_fields={
            "national_id": "SENSITIVE_TEST_VALUE"
        },
        analyzer_version="rules-v1",
    )


def make_risk_result(agent_id=None):
    return RiskAssessmentResult(
        agent_id=agent_id or uuid.uuid4(),
        risk_score=42,
        risk_level=RiskLevel.MEDIUM,
        model_version="rules-v1",
    )


def mock_found_record(db, record):
    db.execute.return_value.scalar_one_or_none.return_value = record


def mock_missing_record(db):
    db.execute.return_value.scalar_one_or_none.return_value = None


def test_save_document_analysis():
    db = MagicMock()
    agent_id = uuid.uuid4()
    result = make_document_result()

    mock_found_record(
        db,
        SimpleNamespace(
            id=result.document_id,
            agent_id=agent_id,
            document_type=result.document_type,
        ),
    )

    check = save_document_analysis(db, agent_id, result)

    assert isinstance(check, VerificationCheck)
    assert check.agent_id == agent_id
    assert check.status == CheckStatus.NEEDS_REVIEW
    assert check.result_data["document_id"] == str(
        result.document_id
    )

    assert "extracted_fields" not in check.result_data
    assert "SENSITIVE_TEST_VALUE" not in str(
        check.result_data
    )

    added = [
        call.args[0] for call in db.add.call_args_list
    ]

    assert len(added) == 2
    assert any(isinstance(x, AuditLog) for x in added)

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(check)


def test_rejects_missing_or_foreign_document():
    db = MagicMock()
    mock_missing_record(db)

    with pytest.raises(VerificationIntegrityError):
        save_document_analysis(
            db,
            uuid.uuid4(),
            make_document_result(),
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_rejects_document_type_mismatch():
    db = MagicMock()
    result = make_document_result(
        document_type="national_id_front"
    )

    mock_found_record(
        db,
        SimpleNamespace(
            document_type="passport",
        ),
    )

    with pytest.raises(VerificationIntegrityError):
        save_document_analysis(
            db,
            uuid.uuid4(),
            result,
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_save_risk_assessment():
    db = MagicMock()
    result = make_risk_result()

    mock_found_record(
        db,
        SimpleNamespace(id=result.agent_id),
    )

    assessment = save_risk_assessment(db, result)

    assert isinstance(assessment, FraudAssessment)
    assert assessment.agent_id == result.agent_id
    assert assessment.risk_score == 42
    assert assessment.risk_level == "medium"

    assert db.add.call_count == 2
    db.commit.assert_called_once()


def test_reuses_existing_phase_ten_assessment_key():
    db = MagicMock()
    result = make_risk_result()
    existing = SimpleNamespace(
        id=uuid.uuid4(),
        agent_id=result.agent_id,
    )
    agent_result = MagicMock()
    agent_result.scalar_one_or_none.return_value = SimpleNamespace(
        id=result.agent_id
    )
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = existing
    db.execute.side_effect = [agent_result, existing_result]

    assessment = save_risk_assessment(
        db,
        result,
        assessment_key="x" * 64,
    )

    assert assessment is existing
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_rejects_nonexistent_agent():
    db = MagicMock()
    mock_missing_record(db)

    with pytest.raises(VerificationIntegrityError):
        save_risk_assessment(
            db,
            make_risk_result(),
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_document_analysis_rollback_on_failure():
    db = MagicMock()
    result = make_document_result()

    mock_found_record(
        db,
        SimpleNamespace(
            document_type=result.document_type,
        ),
    )

    db.commit.side_effect = RuntimeError(
        "Simulated database failure"
    )

    with pytest.raises(VerificationPersistenceError):
        save_document_analysis(
            db,
            uuid.uuid4(),
            result,
        )

    db.rollback.assert_called_once()


def test_risk_assessment_rollback_on_failure():
    db = MagicMock()
    result = make_risk_result()

    mock_found_record(
        db,
        SimpleNamespace(id=result.agent_id),
    )

    db.commit.side_effect = RuntimeError(
        "Simulated database failure"
    )

    with pytest.raises(VerificationPersistenceError):
        save_risk_assessment(db, result)

    db.rollback.assert_called_once()


def test_document_analysis_audit_is_atomic():
    db = MagicMock()
    result = make_document_result()

    mock_found_record(
        db,
        SimpleNamespace(
            document_type=result.document_type,
        ),
    )

    db.commit.side_effect = RuntimeError(
        "Transaction failed"
    )

    with pytest.raises(VerificationPersistenceError):
        save_document_analysis(
            db,
            uuid.uuid4(),
            result,
        )

    assert db.add.call_count == 2
    db.commit.assert_called_once()
    db.rollback.assert_called_once()
