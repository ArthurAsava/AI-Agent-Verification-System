
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent

load_dotenv(PROJECT_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env", override=True)

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    Agent,
    AuditLog,
    FraudAssessment,
    KYCDocument,
    VerificationCheck,
)
from app.services.verification.contracts import (
    DocumentAnalysisResult,
    FraudIndicator,
    RiskAssessmentResult,
    RiskLevel,
    VerificationOutcome,
)
from app.services.verification.persistence import (
    VerificationIntegrityError,
    save_document_analysis,
    save_risk_assessment,
)


pytestmark = pytest.mark.integration


@pytest.fixture
def db():
    """
    Opt-in PostgreSQL integration fixture.

    Each test uses an outer transaction. Commits made by the
    application session are contained in a SAVEPOINT.
    The outer transaction is rolled back during cleanup.
    """
    if os.getenv("RUN_VERIFICATION_DB_TESTS") != "1":
        pytest.skip("Live verification database tests not enabled")

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        pytest.fail("DATABASE_URL must be configured")

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
    )

    try:
        with engine.connect() as connection:
            transaction = connection.begin()

            try:
                with Session(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                    expire_on_commit=False,
                ) as session:
                    yield session
            finally:
                if transaction.is_active:
                    transaction.rollback()
    finally:
        engine.dispose()


def get_existing_agent(db):
    agent = db.execute(
        select(Agent).limit(1)
    ).scalar_one_or_none()

    if agent is None:
        pytest.fail(
            "No development agent exists. "
            "Create a dedicated test agent before running "
            "the integration suite."
        )

    return agent


def get_existing_document(db):
    document = db.execute(
        select(KYCDocument).limit(1)
    ).scalar_one_or_none()

    if document is None:
        pytest.fail(
            "No development KYC document exists. "
            "Create a dedicated test document first."
        )

    return document


def test_live_document_analysis_and_audit(db):
    document = get_existing_document(db)

    result = DocumentAnalysisResult(
        document_id=document.id,
        document_type=document.document_type,
        outcome=VerificationOutcome.NEEDS_REVIEW,
        analyzer_version="integration-test-v1",
    )

    check = save_document_analysis(
        db=db,
        agent_id=document.agent_id,
        result=result,
    )

    stored_check = db.get(VerificationCheck, check.id)

    assert stored_check is not None
    assert stored_check.agent_id == document.agent_id
    assert stored_check.result_data["document_id"] == str(
        document.id
    )

    audit = db.execute(
        select(AuditLog).where(
            AuditLog.agent_id == document.agent_id,
            AuditLog.action == "document_analysis_recorded",
            AuditLog.details["document_id"].astext
            == str(document.id),
        ).order_by(AuditLog.created_at.desc())
    ).scalars().first()

    assert audit is not None


def test_live_rejects_wrong_document_owner(db):
    document = get_existing_document(db)

    result = DocumentAnalysisResult(
        document_id=document.id,
        document_type=document.document_type,
        outcome=VerificationOutcome.PASS,
        analyzer_version="integration-test-v1",
    )

    wrong_agent_id = uuid.uuid4()

    with pytest.raises(VerificationIntegrityError):
        save_document_analysis(
            db=db,
            agent_id=wrong_agent_id,
            result=result,
        )


def test_live_risk_assessment_and_audit(db):
    agent = get_existing_agent(db)

    result = RiskAssessmentResult(
        agent_id=agent.id,
        risk_score=35,
        risk_level=RiskLevel.MEDIUM,
        model_version="integration-test-v1",
    )

    assessment = save_risk_assessment(
        db=db,
        result=result,
    )

    stored_assessment = db.get(
        FraudAssessment,
        assessment.id,
    )

    assert stored_assessment is not None
    assert float(stored_assessment.risk_score) == 35
    assert stored_assessment.risk_level == "medium"

    audit = db.execute(
        select(AuditLog).where(
            AuditLog.agent_id == agent.id,
            AuditLog.action == "fraud_assessment_recorded",
            AuditLog.details["model_version"].astext
            == "integration-test-v1",
        ).order_by(AuditLog.created_at.desc())
    ).scalars().first()

    assert audit is not None


def test_live_phase_ten_evidence_is_idempotent_and_minimized(db):
    agent = get_existing_agent(db)
    result = RiskAssessmentResult(
        agent_id=agent.id,
        risk_score=45,
        risk_level=RiskLevel.HIGH,
        model_version="risk-rules-v2",
        requires_review=True,
        indicators=[
            FraudIndicator(
                code="DUPLICATE_DOCUMENT",
                description=(
                    "The same document checksum is associated with another agent."
                ),
                severity=RiskLevel.HIGH,
                evidence={
                    "weight": 45,
                    "matched_other_agent_documents": 1,
                },
            )
        ],
    )
    assessment_key = f"integration-{uuid.uuid4().hex}"

    first = save_risk_assessment(
        db=db,
        result=result,
        assessment_key=assessment_key,
    )
    repeated = save_risk_assessment(
        db=db,
        result=result,
        assessment_key=assessment_key,
    )

    assert repeated.id == first.id
    stored = db.get(FraudAssessment, first.id)
    assert stored is not None
    assert stored.assessment_key == assessment_key
    assert stored.requires_review is True
    assert stored.signals == [
        {
            "code": "DUPLICATE_DOCUMENT",
            "description": (
                "The same document checksum is associated with another agent."
            ),
            "severity": "high",
            "evidence": {
                "weight": 45,
                "matched_other_agent_documents": 1,
            },
        }
    ]


def test_live_rejects_nonexistent_agent(db):
    result = RiskAssessmentResult(
        agent_id=uuid.uuid4(),
        risk_score=80,
        risk_level=RiskLevel.HIGH,
        model_version="integration-test-v1",
    )

    with pytest.raises(VerificationIntegrityError):
        save_risk_assessment(
            db=db,
            result=result,
        )
