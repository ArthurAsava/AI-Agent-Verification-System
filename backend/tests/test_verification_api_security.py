
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_agent_verification_requires_auth(client):
    response = client.get("/verification/me")

    assert response.status_code == 401


def test_document_submission_requires_auth(client):
    response = client.post(
        f"/verification/documents/{uuid4()}/submit"
    )

    assert response.status_code == 401


def test_review_queue_requires_auth(client):
    response = client.get("/verification/review-queue")

    assert response.status_code == 401


def test_case_details_require_auth(client):
    response = client.get(
        f"/verification/cases/{uuid4()}"
    )

    assert response.status_code == 401


def test_reviewer_decision_requires_auth(client):
    response = client.post(
        f"/verification/cases/{uuid4()}/decision",
        json={
            "action": "approve",
            "reason": "Evidence reviewed and accepted.",
            "expected_version": 0,
        },
    )

    assert response.status_code == 401


def test_invalid_case_id_is_rejected(client):
    response = client.get(
        "/verification/cases/not-a-valid-uuid"
    )

    assert response.status_code == 401


from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db


def test_regular_agent_cannot_access_review_queue():
    user_id = uuid4()

    def override_user():
        return CurrentUser(
            id=user_id,
            email="agent@example.test",
        )

    mock_db = Mock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as client:
            response = client.get(
                "/verification/review-queue"
            )

        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_regular_agent_cannot_submit_decision():
    user_id = uuid4()

    def override_user():
        return CurrentUser(
            id=user_id,
            email="agent@example.test",
        )

    mock_db = Mock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as client:
            response = client.post(
                f"/verification/cases/{uuid4()}/decision",
                json={
                    "action": "approve",
                    "reason": "Attempted unauthorized approval.",
                    "expected_version": 0,
                },
            )

        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_active_reviewer_can_access_review_queue():
    user_id = uuid4()

    def override_user():
        return CurrentUser(
            id=user_id,
            email="reviewer@example.test",
        )

    reviewer = Mock(user_id=user_id, is_active=True)
    reviewer_result = Mock()
    reviewer_result.scalar_one_or_none.return_value = reviewer
    queue_result = Mock()
    queue_result.scalars.return_value.all.return_value = []

    mock_db = Mock()
    mock_db.execute.side_effect = [reviewer_result, queue_result]

    def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as client:
            response = client.get("/verification/review-queue")

        assert response.status_code == 200
        assert response.json() == {"cases": []}
    finally:
        app.dependency_overrides.clear()


def test_reviewer_can_read_minimized_fraud_evidence_for_case():
    reviewer_id = uuid4()
    case_id = uuid4()
    agent_id = uuid4()
    document_id = uuid4()
    now = datetime.now(timezone.utc)

    def override_user():
        return CurrentUser(
            id=reviewer_id,
            email="reviewer@example.test",
        )

    reviewer_result = Mock()
    reviewer_result.scalar_one_or_none.return_value = SimpleNamespace(
        user_id=reviewer_id,
        is_active=True,
    )
    case_result = Mock()
    case_result.scalar_one_or_none.return_value = SimpleNamespace(
        id=case_id,
        agent_id=agent_id,
        document_id=document_id,
        status="awaiting_review",
        version=1,
        created_at=now,
        updated_at=now,
        recommendation="escalate",
        risk_score=80,
        risk_level="critical",
        scoring_version="risk-rules-v2",
        reviewer_user_id=None,
        decision_reason=None,
        reviewed_at=None,
    )
    assessment_result = Mock()
    assessment_result.scalar_one_or_none.return_value = SimpleNamespace(
        id=uuid4(),
        risk_score=80,
        risk_level="critical",
        model_version="risk-rules-v2",
        requires_review=True,
        signals=[
            {
                "code": "DUPLICATE_DOCUMENT",
                "description": "The same document checksum is associated with another agent.",
                "severity": "high",
                "evidence": {"weight": 45, "matched_other_agent_documents": 1},
            }
        ],
        created_at=now,
    )

    mock_db = Mock()
    mock_db.execute.side_effect = [
        reviewer_result,
        case_result,
        assessment_result,
    ]

    def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as client:
            response = client.get(f"/verification/cases/{case_id}")

        assert response.status_code == 200
        payload = response.json()["fraud_assessment"]
        assert payload["risk_level"] == "critical"
        assert payload["signals"] == [
            {
                "code": "DUPLICATE_DOCUMENT",
                "description": "The same document checksum is associated with another agent.",
                "severity": "high",
                "evidence": {
                    "weight": 45,
                    "matched_other_agent_documents": 1,
                },
            }
        ]
    finally:
        app.dependency_overrides.clear()
