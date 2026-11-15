
import uuid

import pytest
from pydantic import ValidationError

from app.services.verification.contracts import (
    DocumentAnalysisResult,
    FraudIndicator,
    RiskAssessmentResult,
    RiskLevel,
    VerificationOutcome,
)


def test_document_analysis_result_is_valid():
    result = DocumentAnalysisResult(
        document_id=uuid.uuid4(),
        document_type="national_id_front",
        outcome=VerificationOutcome.NEEDS_REVIEW,
        analyzer_version="rules-v1",
    )

    assert result.outcome == VerificationOutcome.NEEDS_REVIEW
    assert result.extracted_fields == {}
    assert result.warnings == []


def test_fraud_indicator_is_valid():
    indicator = FraudIndicator(
        code="DUPLICATE_DOCUMENT",
        description="A duplicate document was detected.",
        severity=RiskLevel.HIGH,
    )

    assert indicator.code == "DUPLICATE_DOCUMENT"
    assert indicator.severity == RiskLevel.HIGH


def test_risk_score_cannot_exceed_100():
    with pytest.raises(ValidationError):
        RiskAssessmentResult(
            agent_id=uuid.uuid4(),
            risk_score=120,
            risk_level=RiskLevel.HIGH,
            model_version="rules-v1",
        )


def test_risk_score_cannot_be_negative():
    with pytest.raises(ValidationError):
        RiskAssessmentResult(
            agent_id=uuid.uuid4(),
            risk_score=-5,
            risk_level=RiskLevel.LOW,
            model_version="rules-v1",
        )


def test_valid_risk_assessment():
    result = RiskAssessmentResult(
        agent_id=uuid.uuid4(),
        risk_score=45,
        risk_level=RiskLevel.MEDIUM,
        model_version="rules-v1",
    )

    assert result.risk_score == 45
    assert result.risk_level == RiskLevel.MEDIUM


def test_unexpected_fields_are_rejected():
    with pytest.raises(ValidationError):
        FraudIndicator(
            code="TEST",
            description="Test indicator",
            severity=RiskLevel.LOW,
            secret_token="not-allowed",
        )
