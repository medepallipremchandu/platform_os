"""Tenant isolation: one organization must never see or touch another's telephony credentials,
call agent configs, calls, or any of a call's child records.

Isolation here is enforced in the service layer, not by a database constraint - `visible_query`
scopes on `organization_id`, and the child records (events, conversation turns, summaries) are
reached only through a Call that was already org-checked. Nothing in the schema stops a refactor
from dropping that filter, so these tests are what would notice.

The telephony provider config is the sharpest case: it holds encrypted carrier credentials, so a
leak there is not a privacy problem, it is someone else's phone bill.
"""
import uuid

from app.core import permissions
from tests.conftest import auth_headers
from tests.test_call_agents import _create_call_agent
from tests.test_providers import _create_provider


def _two_orgs():
    return uuid.uuid4(), uuid.uuid4()


# --- Telephony provider configs ----------------------------------------------------------------


def test_a_provider_config_from_another_org_is_not_listed(client):
    org_a, org_b = _two_orgs()
    _create_provider(client, org_b)

    response = client.get(
        "/providers", headers=auth_headers(org_id=org_a, permissions=[permissions.PROVIDERS_READ])
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_a_provider_config_from_another_org_cannot_be_read_by_id(client):
    org_a, org_b = _two_orgs()
    provider_b = _create_provider(client, org_b).json()["id"]

    headers = auth_headers(org_id=org_a, permissions=[permissions.PROVIDERS_READ, permissions.PROVIDERS_MANAGE])
    assert client.patch(
        f"/providers/{provider_b}", json={"name": "stolen"}, headers=headers
    ).status_code == 404
    assert client.delete(f"/providers/{provider_b}", headers=headers).status_code == 404


# --- Call agent configs --------------------------------------------------------------------------


def test_a_call_agent_config_from_another_org_is_invisible(client):
    org_a, org_b = _two_orgs()
    provider_b = _create_provider(client, org_b).json()["id"]
    config_b = _create_call_agent(client, org_b, provider_b).json()["id"]

    read_headers = auth_headers(org_id=org_a, permissions=[permissions.CALLAGENTS_READ])
    assert client.get("/call-agents", headers=read_headers).json()["items"] == []
    assert client.get(f"/call-agents/{config_b}", headers=read_headers).status_code == 404

    write_headers = auth_headers(org_id=org_a, permissions=[permissions.CALLAGENTS_WRITE])
    assert client.patch(f"/call-agents/{config_b}", json={"name": "stolen"}, headers=write_headers).status_code == 404


def test_a_call_cannot_be_placed_with_another_orgs_provider(client):
    """The one that actually costs money: billing another tenant's carrier account."""
    org_a, org_b = _two_orgs()
    provider_b = _create_provider(client, org_b).json()["id"]

    response = client.post(
        "/calls",
        json={
            "to_number": "+15550000000",
            "telephony_provider_config_id": provider_b,
            "call_script": {"persona": "You are Ava.", "objective": "Screen the candidate.", "fields": []},
            "max_conversation_duration_minutes": 5,
        },
        headers=auth_headers(org_id=org_a, permissions=[permissions.CALLS_WRITE]),
    )
    assert response.status_code == 404


# --- Calls and their children ---------------------------------------------------------------------


def _place_call(client, monkeypatch, org_id):
    from tests.test_calls import _stub_telephony

    _stub_telephony(monkeypatch)
    provider_id = _create_provider(client, org_id).json()["id"]
    response = client.post(
        "/calls",
        json={
            "to_number": "+15551234567",
            "telephony_provider_config_id": provider_id,
            "call_script": {"persona": "You are Ava.", "objective": "Screen the candidate.", "fields": []},
            "max_conversation_duration_minutes": 5,
        },
        headers=auth_headers(org_id=org_id, permissions=[permissions.CALLS_WRITE]),
    )
    assert response.status_code in (200, 201, 202), response.text
    return response.json()["id"]


def test_a_call_and_all_of_its_children_are_invisible_to_another_org(client, monkeypatch):
    """`call_events`, `conversation_turns` and `call_summaries` carry no organization_id at all -
    they are reachable only through a Call the service layer has already scoped. If that check
    were dropped, a transcript of someone else's candidate interview would be readable by id."""
    org_a, org_b = _two_orgs()
    call_b = _place_call(client, monkeypatch, org_b)

    headers = auth_headers(org_id=org_a, permissions=[permissions.CALLS_READ])
    assert client.get("/calls", headers=headers).json()["items"] == []
    for path in ("", "/events", "/conversation", "/summary"):
        assert client.get(f"/calls/{call_b}{path}", headers=headers).status_code == 404, path


def test_another_org_cannot_cancel_a_call(client, monkeypatch):
    org_a, org_b = _two_orgs()
    call_b = _place_call(client, monkeypatch, org_b)

    response = client.post(
        f"/calls/{call_b}/cancel",
        json={"graceful": True},
        headers=auth_headers(org_id=org_a, permissions=[permissions.CALLS_WRITE]),
    )
    assert response.status_code == 404


def test_the_owning_org_can_still_read_its_own_call_and_children(client, monkeypatch):
    """The other half: an isolation filter that rejects everyone is not isolation, it is an outage."""
    org_a = uuid.uuid4()
    call_a = _place_call(client, monkeypatch, org_a)

    headers = auth_headers(org_id=org_a, permissions=[permissions.CALLS_READ])
    assert client.get(f"/calls/{call_a}", headers=headers).status_code == 200
    assert client.get(f"/calls/{call_a}/events", headers=headers).status_code == 200
    assert client.get(f"/calls/{call_a}/conversation", headers=headers).status_code == 200
    assert [row["id"] for row in client.get("/calls", headers=headers).json()["items"]] == [call_a]
