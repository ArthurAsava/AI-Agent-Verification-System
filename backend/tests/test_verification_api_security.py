
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


def test_admin_summary_requires_auth(client):
    response = client.get("/verification/admin/summary")

    assert response.status_code == 401


def test_admin_agent_directory_requires_auth(client):
    response = client.get("/verification/admin/agents/waiting")

    assert response.status_code == 401


from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db
from app.models.entities import AgentStatus


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


def test_active_reviewer_cannot_access_administration():
    user_id = uuid4()

    def override_user():
        return CurrentUser(
            id=user_id,
            email="reviewer@example.test",
        )

    mock_db = Mock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as client:
            response = client.get("/verification/admin/summary")

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


def test_active_administrator_can_read_dashboard_summary():
    user_id = uuid4()

    def override_user():
        return CurrentUser(
            id=user_id,
            email="admin@example.test",
        )

    administrator_result = Mock()
    administrator_result.scalar_one_or_none.return_value = SimpleNamespace(
        user_id=user_id,
        is_active=True,
        is_admin=True,
    )
    counts = []
    for value in (3, 2, 4, 5, 6, 7, 8, 9):
        count_result = Mock()
        count_result.scalar_one.return_value = value
        counts.append(count_result)
    mock_db = Mock()
    mock_db.execute.side_effect = [administrator_result, *counts]

    def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as client:
            response = client.get("/verification/admin/summary")

        assert response.status_code == 200
        assert response.json() == {
            "awaiting_review_cases": 3,
            "elevated_risk_cases": 2,
            "new_cases_last_24_hours": 4,
            "agents_under_review": 5,
            "active_reviewers": 6,
            "waiting_agents": 7,
            "approved_agents": 8,
            "rejected_agents": 9,
        }
    finally:
        app.dependency_overrides.clear()


def test_active_administrator_can_read_agent_category():
    user_id = uuid4()
    agent_id = uuid4()
    now = datetime.now(timezone.utc)

    def override_user():
        return CurrentUser(id=user_id, email="admin@example.test")

    administrator_result = Mock()
    administrator_result.scalar_one_or_none.return_value = user_id
    agents_result = Mock()
    agents_result.scalars.return_value.all.return_value = [
        SimpleNamespace(
            id=agent_id,
            user_id=uuid4(),
            first_name="Regular",
            last_name="Agent",
            phone_number="+254700000000",
            date_of_birth=None,
            primary_residence="Nairobi",
            nationality="Kenyan",
            avatar_variant=None,
            status=AgentStatus.UNDER_REVIEW,
            created_at=now,
            updated_at=now,
        )
    ]
    mock_db = Mock()
    mock_db.execute.side_effect = [administrator_result, agents_result]

    def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as client:
            response = client.get("/verification/admin/agents/waiting")

        assert response.status_code == 200
        assert response.json()["category"] == "waiting"
        assert response.json()["agents"][0]["id"] == str(agent_id)
        assert response.json()["agents"][0]["status"] == "under_review"
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
