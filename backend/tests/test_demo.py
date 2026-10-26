
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_valid_demo_request():
    response = client.post(
        "/api/v1/demo/validate",
        json={"name": "Test Agent", "age": 25},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Validation successful"


def test_invalid_demo_request():
    response = client.post(
        "/api/v1/demo/validate",
        json={"name": "A", "age": 15},
    )

    assert response.status_code == 422


def test_custom_error():
    response = client.get("/api/v1/demo/error")

    assert response.status_code == 400
    assert response.json() == {
        "error": "DEMO_ERROR",
        "message": "Demonstration error",
    }
