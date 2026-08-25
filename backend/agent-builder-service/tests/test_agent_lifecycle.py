"""Covers the enterprise-hardening additions: agent archive (soft-delete, credential
revocation, no republish-after-archive, no edit-after-archive) and model PATCH
(rename/re-credential without touching provider/model_id). Mirrors test_health.py's pattern of
overriding `current_actor` rather than minting a real iam-service JWT."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.iam_client import CurrentActor, current_actor
from app.core.permissions import AGENTS_PUBLISH, AGENTS_READ, AGENTS_WRITE, MODELS_MANAGE
from app.database import SessionLocal
from app.main import app
from app.models.agent import Agent
from app.models.agent_credential import AgentCredential
from app.models.model import Model
from app.services import agent_credentials

client = TestClient(app)

ORG_ID = "22222222-2222-2222-2222-222222222222"
ALL_PERMS = [AGENTS_READ, AGENTS_WRITE, AGENTS_PUBLISH, MODELS_MANAGE, "talentos.agentbuilder.agents.manage_keys"]


def _actor(permissions=None) -> CurrentActor:
    return CurrentActor(
        principal_type="user",
        id="11111111-1111-1111-1111-111111111111",
        org_id=ORG_ID,
        permissions=permissions if permissions is not None else ALL_PERMS,
        resource_scope=None,
        email_or_name="test@example.com",
    )


@pytest.fixture(autouse=True)
def _as_admin():
    app.dependency_overrides[current_actor] = _actor
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _fake_iam_service_principals(monkeypatch):
    """Publish/archive call out to iam-service to mint/revoke a ServicePrincipal - fake that
    boundary so these tests don't depend on iam-service actually running."""
    store: dict[str, bool] = {}

    def fake_create(*, agent_name, organization_id, agent_id):
        sp_id = str(uuid.uuid4())
        store[sp_id] = False
        return {"service_principal": {"id": sp_id, "client_id": f"spid_{sp_id[:8]}"}, "client_secret": "secret-once"}

    def fake_revoke(*, service_principal_id):
        assert service_principal_id in store
        store[service_principal_id] = True

    monkeypatch.setattr(agent_credentials, "create_resource_bound_service_principal", fake_create)
    monkeypatch.setattr(agent_credentials, "revoke_service_principal", fake_revoke)
    yield store


AUTH = {"Authorization": "Bearer whatever"}

_created_agent_ids: list[str] = []
_created_model_ids: list[str] = []


@pytest.fixture(autouse=True)
def _cleanup_created_rows():
    """These tests hit the real dev Postgres DB (see test_health.py's own precedent - `get_db`
    isn't overridden). Hard-delete whatever this test created afterward so repeated local/CI
    runs don't pile up 'Lifecycle Test Agent' rows forever - this is disposable test fixture
    data, not production content, so bypassing the app's own soft-delete semantics here is fine."""
    yield
    db = SessionLocal()
    try:
        if _created_agent_ids:
            db.query(AgentCredential).filter(AgentCredential.agent_id.in_(_created_agent_ids)).delete(
                synchronize_session=False
            )
            db.query(Agent).filter(Agent.id.in_(_created_agent_ids)).delete(synchronize_session=False)
        if _created_model_ids:
            db.query(Model).filter(Model.id.in_(_created_model_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        _created_agent_ids.clear()
        _created_model_ids.clear()
        db.close()


def _make_model() -> str:
    resp = client.post(
        "/api/v1/models",
        json={"name": "Lifecycle Test Model", "provider": "claude", "model_id": "claude-sonnet-5", "api_key": "sk-x"},
        headers=AUTH,
    )
    assert resp.status_code == 201
    model_id = resp.json()["id"]
    _created_model_ids.append(model_id)
    return model_id


def _make_agent(model_id: str) -> str:
    resp = client.post(
        "/api/v1/agents",
        json={
            "name": "Lifecycle Test Agent",
            "system_prompt": "sys",
            "user_prompt_template": "{{x}}",
            "primary_model_id": model_id,
        },
        headers=AUTH,
    )
    assert resp.status_code == 201
    agent_id = resp.json()["id"]
    _created_agent_ids.append(agent_id)
    return agent_id


def test_archive_draft_agent_soft_deletes():
    model_id = _make_model()
    agent_id = _make_agent(model_id)

    resp = client.delete(f"/api/v1/agents/{agent_id}", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "archived"
    assert body["archived_at"] is not None


def test_archived_agent_excluded_from_default_list_but_visible_with_include_archived():
    model_id = _make_model()
    agent_id = _make_agent(model_id)
    client.delete(f"/api/v1/agents/{agent_id}", headers=AUTH)

    default_ids = [a["id"] for a in client.get("/api/v1/agents", headers=AUTH).json()]
    assert agent_id not in default_ids

    all_ids = [a["id"] for a in client.get("/api/v1/agents?include_archived=true", headers=AUTH).json()]
    assert agent_id in all_ids


def test_double_archive_is_rejected():
    model_id = _make_model()
    agent_id = _make_agent(model_id)
    assert client.delete(f"/api/v1/agents/{agent_id}", headers=AUTH).status_code == 200
    assert client.delete(f"/api/v1/agents/{agent_id}", headers=AUTH).status_code == 422


def test_archiving_published_agent_revokes_its_credential(_fake_iam_service_principals):
    model_id = _make_model()
    agent_id = _make_agent(model_id)
    assert client.post(f"/api/v1/agents/{agent_id}/publish", headers=AUTH).status_code == 200

    keys_before = client.get(f"/api/v1/agents/{agent_id}/keys", headers=AUTH).json()
    assert len(keys_before) == 1
    assert keys_before[0]["revoked_at"] is None

    assert client.delete(f"/api/v1/agents/{agent_id}", headers=AUTH).status_code == 200

    keys_after = client.get(f"/api/v1/agents/{agent_id}/keys", headers=AUTH).json()
    assert keys_after[0]["revoked_at"] is not None
    assert all(_fake_iam_service_principals.values()), "iam-service revoke should have been called"


def test_archived_agent_cannot_be_republished():
    model_id = _make_model()
    agent_id = _make_agent(model_id)
    client.post(f"/api/v1/agents/{agent_id}/publish", headers=AUTH)
    client.delete(f"/api/v1/agents/{agent_id}", headers=AUTH)

    resp = client.post(f"/api/v1/agents/{agent_id}/publish", headers=AUTH)
    assert resp.status_code == 422


def test_archived_agent_cannot_be_edited():
    model_id = _make_model()
    agent_id = _make_agent(model_id)
    client.delete(f"/api/v1/agents/{agent_id}", headers=AUTH)

    resp = client.patch(f"/api/v1/agents/{agent_id}", json={"description": "nope"}, headers=AUTH)
    assert resp.status_code == 422


def test_archive_requires_agents_publish_permission():
    model_id = _make_model()
    agent_id = _make_agent(model_id)

    app.dependency_overrides[current_actor] = lambda: _actor(permissions=[AGENTS_READ, AGENTS_WRITE])
    resp = client.delete(f"/api/v1/agents/{agent_id}", headers=AUTH)
    assert resp.status_code == 403


def test_model_patch_renames_and_reencrypts_credential_without_touching_provider():
    model_id = _make_model()
    original = client.get(f"/api/v1/models/{model_id}", headers=AUTH).json()

    resp = client.patch(f"/api/v1/models/{model_id}", json={"name": "Renamed Model"}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed Model"
    assert resp.json()["provider"] == original["provider"]
    assert resp.json()["model_id"] == original["model_id"]

    resp2 = client.patch(f"/api/v1/models/{model_id}", json={"api_key": "sk-rotated"}, headers=AUTH)
    assert resp2.status_code == 200
    assert resp2.json()["provider"] == original["provider"]
    assert resp2.json()["model_id"] == original["model_id"]


def test_model_patch_requires_models_manage_permission():
    model_id = _make_model()
    app.dependency_overrides[current_actor] = lambda: _actor(permissions=[AGENTS_READ])
    resp = client.patch(f"/api/v1/models/{model_id}", json={"name": "nope"}, headers=AUTH)
    assert resp.status_code == 403
