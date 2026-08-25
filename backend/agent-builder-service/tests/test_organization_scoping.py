"""Tenant isolation: one organization must never see or touch another's models or agents.

Two things make this worth pinning down rather than assuming.

A model row holds a provider API key (encrypted, but reusable through this service's own
/invoke path), and an agent holds the system and user prompts - the actual intellectual property
a tenant is paying to keep private. Leaking either is materially worse than leaking a list of
names.

And `organization_id` here comes from the caller's token, never from the request body, so the
only thing standing between tenants is the service layer remembering to filter. Nothing in the
schema enforces it.

Like the rest of this service's tests these run against the real dev Postgres (get_db is not
overridden), so every row created is hard-deleted afterwards.
"""
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

client = TestClient(app)

AUTH = {"Authorization": "Bearer whatever"}
ALL_PERMS = [AGENTS_READ, AGENTS_WRITE, AGENTS_PUBLISH, MODELS_MANAGE, "talentos.agentbuilder.agents.manage_keys"]

ORG_A = "aaaaaaaa-0000-4000-8000-000000000001"
ORG_B = "bbbbbbbb-0000-4000-8000-000000000002"

_created_agent_ids: list[str] = []
_created_model_ids: list[str] = []


def _actor_for(org_id: str) -> CurrentActor:
    return CurrentActor(
        principal_type="user",
        id="11111111-1111-1111-1111-111111111111",
        org_id=org_id,
        permissions=ALL_PERMS,
        resource_scope=None,
        email_or_name=f"tester-{org_id[:4]}@example.com",
    )


def _act_as(org_id: str) -> None:
    """Swap which organization the caller belongs to. The whole point of these tests is that
    nothing else about the request changes - same permissions, same everything - and the answer
    still has to change."""
    app.dependency_overrides[current_actor] = lambda: _actor_for(org_id)


@pytest.fixture(autouse=True)
def _isolate_and_cleanup():
    _act_as(ORG_A)
    yield
    app.dependency_overrides.clear()
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
        db.close()
        _created_agent_ids.clear()
        _created_model_ids.clear()


def _make_model(org_id: str, name="Scoping Test Model") -> str:
    _act_as(org_id)
    response = client.post(
        "/api/v1/models",
        json={"name": name, "provider": "claude", "model_id": "claude-sonnet-5", "api_key": "sk-secret"},
        headers=AUTH,
    )
    assert response.status_code == 201, response.text
    model_id = response.json()["id"]
    _created_model_ids.append(model_id)
    return model_id


def _make_agent(org_id: str, model_id: str, name="Scoping Test Agent") -> str:
    _act_as(org_id)
    response = client.post(
        "/api/v1/agents",
        json={
            "name": name,
            "system_prompt": "Confidential prompt belonging to one tenant.",
            "user_prompt_template": "{{x}}",
            "primary_model_id": model_id,
        },
        headers=AUTH,
    )
    assert response.status_code == 201, response.text
    agent_id = response.json()["id"]
    _created_agent_ids.append(agent_id)
    return agent_id


# --- Models -------------------------------------------------------------------------------------


def test_models_from_another_org_are_not_listed(client_unused=None):
    model_b = _make_model(ORG_B)

    _act_as(ORG_A)
    ids = [m["id"] for m in client.get("/api/v1/models", headers=AUTH).json()]
    assert model_b not in ids


def test_a_model_from_another_org_cannot_be_read_or_changed(client_unused=None):
    model_b = _make_model(ORG_B)

    _act_as(ORG_A)
    assert client.get(f"/api/v1/models/{model_b}", headers=AUTH).status_code == 404
    assert client.patch(f"/api/v1/models/{model_b}", json={"name": "stolen"}, headers=AUTH).status_code == 404
    assert client.delete(f"/api/v1/models/{model_b}", headers=AUTH).status_code == 404


def test_an_agent_cannot_be_built_on_another_orgs_model(client_unused=None):
    """Otherwise a tenant could point their own agent at someone else's model row and invoke
    against that organization's provider credentials."""
    model_b = _make_model(ORG_B)

    _act_as(ORG_A)
    response = client.post(
        "/api/v1/agents",
        json={
            "name": "Borrowed Model Agent",
            "system_prompt": "sys",
            "user_prompt_template": "{{x}}",
            "primary_model_id": model_b,
        },
        headers=AUTH,
    )
    assert response.status_code == 404, response.text


# --- Agents -------------------------------------------------------------------------------------


def test_agents_from_another_org_are_not_listed(client_unused=None):
    agent_b = _make_agent(ORG_B, _make_model(ORG_B))

    _act_as(ORG_A)
    for query in ("", "?include_archived=true"):
        ids = [a["id"] for a in client.get(f"/api/v1/agents{query}", headers=AUTH).json()]
        assert agent_b not in ids, query


def test_an_agent_from_another_org_is_fully_inaccessible(client_unused=None):
    """Read, edit, publish, archive and its credentials - the prompts are the IP here."""
    agent_b = _make_agent(ORG_B, _make_model(ORG_B))

    _act_as(ORG_A)
    assert client.get(f"/api/v1/agents/{agent_b}", headers=AUTH).status_code == 404
    assert client.patch(f"/api/v1/agents/{agent_b}", json={"name": "stolen"}, headers=AUTH).status_code == 404
    assert client.post(f"/api/v1/agents/{agent_b}/publish", headers=AUTH).status_code == 404
    assert client.get(f"/api/v1/agents/{agent_b}/keys", headers=AUTH).status_code == 404
    assert client.delete(f"/api/v1/agents/{agent_b}", headers=AUTH).status_code == 404


def test_organization_id_comes_from_the_token_not_the_request_body(client_unused=None):
    """A caller must not be able to plant a row in another tenant by naming it in the payload."""
    _act_as(ORG_A)
    response = client.post(
        "/api/v1/models",
        json={
            "name": "Planted Model",
            "provider": "claude",
            "model_id": "claude-sonnet-5",
            "api_key": "sk-x",
            "organization_id": ORG_B,
        },
        headers=AUTH,
    )
    assert response.status_code == 201, response.text
    _created_model_ids.append(response.json()["id"])

    # It landed in the caller's own organization, and org B still cannot see it.
    _act_as(ORG_B)
    assert response.json()["id"] not in [m["id"] for m in client.get("/api/v1/models", headers=AUTH).json()]


def test_the_owning_org_can_still_use_its_own_model_and_agent(client_unused=None):
    """An isolation filter that rejects everyone is not isolation, it is an outage."""
    model_a = _make_model(ORG_A)
    agent_a = _make_agent(ORG_A, model_a)

    _act_as(ORG_A)
    assert client.get(f"/api/v1/models/{model_a}", headers=AUTH).status_code == 200
    assert client.get(f"/api/v1/agents/{agent_a}", headers=AUTH).status_code == 200
    assert agent_a in [a["id"] for a in client.get("/api/v1/agents", headers=AUTH).json()]
