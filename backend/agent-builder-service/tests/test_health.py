from fastapi.testclient import TestClient

from app.core.iam_client import CurrentActor, current_actor
from app.core.permissions import AGENTS_READ
from app.main import app

client = TestClient(app)


def _actor(permissions=None) -> CurrentActor:
    return CurrentActor(
        principal_type="user",
        id="11111111-1111-1111-1111-111111111111",
        org_id="22222222-2222-2222-2222-222222222222",
        permissions=permissions or [],
        resource_scope=None,
        email_or_name="test@example.com",
    )


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_admin_requires_bearer_token():
    response = client.get("/api/v1/agents")
    assert response.status_code == 401


def test_admin_rejects_malformed_token():
    response = client.get("/api/v1/agents", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert response.status_code == 401


def test_admin_enforces_permission():
    app.dependency_overrides[current_actor] = lambda: _actor(permissions=[])
    try:
        response = client.get("/api/v1/agents", headers={"Authorization": "Bearer whatever"})
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_admin_allows_with_permission():
    app.dependency_overrides[current_actor] = lambda: _actor(permissions=[AGENTS_READ])
    try:
        response = client.get("/api/v1/agents", headers={"Authorization": "Bearer whatever"})
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_invoke_requires_bearer_token():
    response = client.post("/api/v1/invoke", json={"variables": {}})
    assert response.status_code == 401


def test_invoke_rejects_malformed_token():
    response = client.post(
        "/api/v1/invoke", json={"variables": {}}, headers={"Authorization": "Bearer not-a-real-jwt"}
    )
    assert response.status_code == 401
