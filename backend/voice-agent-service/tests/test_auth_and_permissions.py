import uuid

from app.core import permissions
from tests.conftest import auth_headers


def test_providers_requires_auth(client):
    assert client.get("/providers").status_code == 401
    assert client.post("/providers", json={}).status_code == 401


def test_call_agents_requires_auth(client):
    assert client.get("/call-agents").status_code == 401


def test_calls_requires_auth(client):
    assert client.get("/calls").status_code == 401
    assert client.post("/calls", json={}).status_code == 401


def test_missing_permission_is_403(client):
    org_id = uuid.uuid4()
    headers = auth_headers(org_id=org_id, permissions=[])
    response = client.get("/providers", headers=headers)
    assert response.status_code == 403


def test_valid_token_with_permission_returns_empty_list(client):
    org_id = uuid.uuid4()
    headers = auth_headers(org_id=org_id, permissions=[permissions.PROVIDERS_READ])
    response = client.get("/providers", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_expired_token_is_401(client):
    org_id = uuid.uuid4()
    headers = auth_headers(org_id=org_id, permissions=[permissions.PROVIDERS_READ], expired=True)
    response = client.get("/providers", headers=headers)
    assert response.status_code == 401
