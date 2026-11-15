
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


DOCUMENT_ID = uuid.uuid4()


@pytest.fixture
def client():
    # Do not bypass authentication for these tests.
    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.clear()

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/kyc/documents",
        f"/api/v1/kyc/documents/{DOCUMENT_ID}",
        f"/api/v1/kyc/documents/{DOCUMENT_ID}/download",
    ],
)
def test_missing_token_is_rejected(client, path):
    response = client.get(path)

    assert response.status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/kyc/documents",
        f"/api/v1/kyc/documents/{DOCUMENT_ID}",
        f"/api/v1/kyc/documents/{DOCUMENT_ID}/download",
    ],
)
def test_invalid_token_is_rejected(client, path):
    response = client.get(
        path,
        headers={
            "Authorization": "Bearer invalid-token"
        },
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/kyc/documents",
        f"/api/v1/kyc/documents/{DOCUMENT_ID}",
        f"/api/v1/kyc/documents/{DOCUMENT_ID}/download",
    ],
)
def test_malformed_authorization_is_rejected(
    client, path
):
    response = client.get(
        path,
        headers={
            "Authorization": "Basic invalid-token"
        },
    )

    assert response.status_code == 401


def test_upload_requires_authentication(client):
    response = client.post(
        "/api/v1/kyc/documents",
        data={
            "document_type": "national_id_front"
        },
        files={
            "file": (
                "test.png",
                b"not-a-real-image",
                "image/png",
            )
        },
    )

    assert response.status_code == 401
