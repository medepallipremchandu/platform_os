def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_v1_requires_bearer_token(client):
    response = client.post("/api/v1/jd-analysis", json={"jd_text": "x" * 25})
    assert response.status_code == 401
