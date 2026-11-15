from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_biometric_review_queue_requires_auth():
    with TestClient(app) as client:
        response = client.get("/verification/biometric-reviews")

    assert response.status_code == 401


def test_biometric_document_download_requires_auth():
    with TestClient(app) as client:
        response = client.get(
            f"/verification/biometric-reviews/{uuid4()}/documents/{uuid4()}/download"
        )

    assert response.status_code == 401


def test_biometric_decision_requires_auth():
    with TestClient(app) as client:
        response = client.post(
            f"/verification/biometric-reviews/{uuid4()}/decision",
            json={
                "action": "confirm_match",
                "reason": "Evidence has been reviewed by a human reviewer.",
            },
        )

    assert response.status_code == 401
