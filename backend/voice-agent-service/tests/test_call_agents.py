import uuid

from app.core import permissions
from tests.conftest import auth_headers
from tests.test_providers import _create_provider


def _create_call_agent(client, org_id, provider_id, email="creator@example.com", **overrides):
    payload = {
        "name": "Scheduling Agent",
        "description": "Confirms appointment times",
        "persona": "You are Ava, a scheduling assistant.",
        "objective": "Confirm the callee's preferred appointment time.",
        "consent_line": "This call may be recorded and is conducted by an AI assistant. Do you consent to continue?",
        "closing_line": "Thanks, have a great day!",
        "fields": [{"name": "preferred_time", "type": "string", "description": "The callee's preferred time"}],
        "max_conversation_duration_minutes": 5,
        "retry_max_attempts": 2,
        "retry_interval_minutes": 15,
        "retry_on_statuses": ["NO_ANSWER", "BUSY"],
        "telephony_provider_config_id": provider_id,
        "visibility": "organization",
        "grant_user_ids": [],
    }
    payload.update(overrides)
    headers = auth_headers(org_id=org_id, permissions=[permissions.CALLAGENTS_WRITE], email=email)
    return client.post("/call-agents", json=payload, headers=headers)


def test_create_call_agent_referencing_provider(client):
    org_id = uuid.uuid4()
    provider_id = _create_provider(client, org_id).json()["id"]

    response = _create_call_agent(client, org_id, provider_id)
    assert response.status_code == 201
    body = response.json()
    assert body["telephony_provider_config_id"] == provider_id
    assert body["retry_max_attempts"] == 2
    assert body["is_active"] is True

    read_headers = auth_headers(org_id=org_id, permissions=[permissions.CALLAGENTS_READ])
    get_response = client.get(f"/call-agents/{body['id']}", headers=read_headers)
    assert get_response.status_code == 200


def test_update_call_agent(client):
    org_id = uuid.uuid4()
    provider_id = _create_provider(client, org_id).json()["id"]
    config_id = _create_call_agent(client, org_id, provider_id).json()["id"]

    write_headers = auth_headers(org_id=org_id, permissions=[permissions.CALLAGENTS_WRITE])
    response = client.patch(f"/call-agents/{config_id}", json={"name": "Renamed Agent"}, headers=write_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Agent"


def test_soft_delete_deactivates_not_hard_deletes(client):
    org_id = uuid.uuid4()
    provider_id = _create_provider(client, org_id).json()["id"]
    config_id = _create_call_agent(client, org_id, provider_id).json()["id"]

    write_headers = auth_headers(org_id=org_id, permissions=[permissions.CALLAGENTS_WRITE])
    delete_response = client.delete(f"/call-agents/{config_id}", headers=write_headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["is_active"] is False

    list_headers = auth_headers(org_id=org_id, permissions=[permissions.CALLAGENTS_READ])
    list_response = client.get("/call-agents", headers=list_headers)
    assert list_response.json()["items"] == []  # inactive configs are excluded from listing

    # But the row itself still exists (a historical Call could still reference it).
    get_response = client.get(f"/call-agents/{config_id}", headers=list_headers)
    assert get_response.status_code == 200

    # ...and is visible again when explicitly asked for via include_inactive=true.
    with_inactive = client.get("/call-agents", params={"include_inactive": "true"}, headers=list_headers)
    items = with_inactive.json()["items"]
    assert len(items) == 1
    assert items[0]["is_active"] is False


def test_restricted_call_agent_visibility(client):
    org_id = uuid.uuid4()
    provider_id = _create_provider(client, org_id).json()["id"]
    create_response = _create_call_agent(
        client, org_id, provider_id, email="alice@example.com", visibility="restricted", grant_user_ids=["bob@example.com"]
    )
    assert create_response.status_code == 201
    config_id = create_response.json()["id"]

    bob_headers = auth_headers(org_id=org_id, permissions=[permissions.CALLAGENTS_READ], email="bob@example.com")
    bob_list = client.get("/call-agents", headers=bob_headers)
    assert len(bob_list.json()["items"]) == 1

    carol_headers = auth_headers(org_id=org_id, permissions=[permissions.CALLAGENTS_READ], email="carol@example.com")
    carol_list = client.get("/call-agents", headers=carol_headers)
    assert carol_list.json()["items"] == []
