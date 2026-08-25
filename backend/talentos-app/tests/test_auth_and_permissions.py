import uuid

from app.core import permissions
from tests.conftest import auth_headers, make_token


def test_missing_token_is_401(client):
    response = client.get("/api/v1/jd-analysis")
    assert response.status_code == 401


def test_invalid_token_is_401(client):
    response = client.get("/api/v1/jd-analysis", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_expired_token_is_401(client):
    org_id = uuid.uuid4()
    headers = auth_headers(org_id=org_id, permissions=[permissions.REQUIREMENTS_READ], expired=True)
    response = client.get("/api/v1/jd-analysis", headers=headers)
    assert response.status_code == 401


def test_wrong_kid_is_401(client):
    org_id = uuid.uuid4()
    token = make_token(org_id=org_id, permissions=[permissions.REQUIREMENTS_READ], kid="unknown-kid")
    response = client.get("/api/v1/jd-analysis", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_missing_permission_is_403(client):
    org_id = uuid.uuid4()
    headers = auth_headers(org_id=org_id, permissions=[permissions.APPLICANTS_READ])  # wrong permission
    response = client.get("/api/v1/jd-analysis", headers=headers)
    assert response.status_code == 403


def test_correct_permission_is_200(client):
    org_id = uuid.uuid4()
    headers = auth_headers(org_id=org_id, permissions=[permissions.REQUIREMENTS_READ])
    response = client.get("/api/v1/jd-analysis", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


def test_delete_requires_delete_permission_not_write(client):
    org_id = uuid.uuid4()
    # write permission alone must not satisfy the delete-scoped endpoint
    headers = auth_headers(org_id=org_id, permissions=[permissions.REQUIREMENTS_WRITE])
    response = client.delete(f"/api/v1/jd-analysis/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 403


def test_health_endpoint_has_no_auth(client):
    response = client.get("/health")
    assert response.status_code == 200
