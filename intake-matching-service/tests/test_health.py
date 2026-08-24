from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_v1_requires_api_key():
    response = client.post("/api/v1/jd-analysis", json={"jd_text": "x" * 25})
    assert response.status_code == 422  # missing header
