import uuid

from app.core import permissions
from tests.conftest import auth_headers
from tests.test_call_agents import _create_call_agent
from tests.test_providers import _create_provider


class _FakeTelephonyProvider:
    async def place_call(self, *, to_number, from_number, call_id, base_url):
        return "CAfakesid0000000000000000000000"

    async def fetch_recording_url(self, provider_call_sid):
        return None


def _fake_get_telephony_provider(provider, credentials):
    return _FakeTelephonyProvider()


def _stub_telephony(monkeypatch):
    monkeypatch.setattr("app.services.calls_service.get_telephony_provider", _fake_get_telephony_provider)


def test_create_inline_call_dials_and_returns_202(client, monkeypatch):
    _stub_telephony(monkeypatch)
    org_id = uuid.uuid4()
    provider_id = _create_provider(client, org_id).json()["id"]

    write_headers = auth_headers(org_id=org_id, permissions=[permissions.CALLS_WRITE])
    response = client.post(
        "/calls",
        json={
            "to_number": "+15551234567",
            "telephony_provider_config_id": provider_id,
            "call_script": {
                "persona": "You are Ava.",
                "objective": "Confirm the appointment.",
                "fields": [],
            },
            "max_conversation_duration_minutes": 5,
        },
        headers=write_headers,
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "DIALING"
    assert body["attempt_number"] == 1
    assert body["retry_max_attempts"] == 0  # inline calls never retry by default


def test_create_call_via_saved_agent_config(client, monkeypatch):
    _stub_telephony(monkeypatch)
    org_id = uuid.uuid4()
    provider_id = _create_provider(client, org_id).json()["id"]
    config_id = _create_call_agent(client, org_id, provider_id).json()["id"]

    write_headers = auth_headers(org_id=org_id, permissions=[permissions.CALLS_WRITE])
    response = client.post(
        "/calls", json={"to_number": "+15551234567", "call_agent_config_id": config_id}, headers=write_headers
    )
    assert response.status_code == 202
    body = response.json()
    assert body["call_agent_config_id"] == config_id
    assert body["retry_max_attempts"] == 2  # snapshot from the saved config


def test_idempotency_key_returns_same_call(client, monkeypatch):
    _stub_telephony(monkeypatch)
    org_id = uuid.uuid4()
    provider_id = _create_provider(client, org_id).json()["id"]

    write_headers = {
        **auth_headers(org_id=org_id, permissions=[permissions.CALLS_WRITE]),
        "Idempotency-Key": "retry-me-once",
    }
    payload = {
        "to_number": "+15551234567",
        "telephony_provider_config_id": provider_id,
        "call_script": {"persona": "You are Ava.", "objective": "Confirm.", "fields": []},
        "max_conversation_duration_minutes": 5,
    }
    first = client.post("/calls", json=payload, headers=write_headers)
    second = client.post("/calls", json=payload, headers=write_headers)
    assert first.json()["id"] == second.json()["id"]


def test_cancel_call(client, monkeypatch):
    _stub_telephony(monkeypatch)
    org_id = uuid.uuid4()
    provider_id = _create_provider(client, org_id).json()["id"]

    write_headers = auth_headers(org_id=org_id, permissions=[permissions.CALLS_WRITE])
    create_response = client.post(
        "/calls",
        json={
            "to_number": "+15551234567",
            "telephony_provider_config_id": provider_id,
            "call_script": {"persona": "You are Ava.", "objective": "Confirm.", "fields": []},
            "max_conversation_duration_minutes": 5,
        },
        headers=write_headers,
    )
    call_id = create_response.json()["id"]

    cancel_response = client.post(f"/calls/{call_id}/cancel", json={"graceful": True}, headers=write_headers)
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "CANCELLED"

    # Already-terminal -> 409 on a second cancel.
    second_cancel = client.post(f"/calls/{call_id}/cancel", json={"graceful": True}, headers=write_headers)
    assert second_cancel.status_code == 409


def test_list_calls_search_filters_by_to_number(client, monkeypatch):
    _stub_telephony(monkeypatch)
    org_id = uuid.uuid4()
    provider_id = _create_provider(client, org_id).json()["id"]

    write_headers = auth_headers(org_id=org_id, permissions=[permissions.CALLS_WRITE])
    for number in ["+15551230001", "+15559990002"]:
        client.post(
            "/calls",
            json={
                "to_number": number,
                "telephony_provider_config_id": provider_id,
                "call_script": {"persona": "You are Ava.", "objective": "Confirm.", "fields": []},
                "max_conversation_duration_minutes": 5,
            },
            headers=write_headers,
        )

    read_headers = auth_headers(org_id=org_id, permissions=[permissions.CALLS_READ])
    response = client.get("/calls", params={"search": "1230001"}, headers=read_headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["to_number"] == "+15551230001"


def test_list_calls_sort_by_attempt_number_ascending(client, monkeypatch):
    _stub_telephony(monkeypatch)
    org_id = uuid.uuid4()
    provider_id = _create_provider(client, org_id).json()["id"]

    write_headers = auth_headers(org_id=org_id, permissions=[permissions.CALLS_WRITE])
    for number in ["+15551110001", "+15551110002"]:
        client.post(
            "/calls",
            json={
                "to_number": number,
                "telephony_provider_config_id": provider_id,
                "call_script": {"persona": "You are Ava.", "objective": "Confirm.", "fields": []},
                "max_conversation_duration_minutes": 5,
            },
            headers=write_headers,
        )

    read_headers = auth_headers(org_id=org_id, permissions=[permissions.CALLS_READ])
    response = client.get("/calls", params={"sort_by": "created_at", "sort_dir": "asc"}, headers=read_headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert [c["to_number"] for c in items] == ["+15551110001", "+15551110002"]


def test_calls_scoped_to_organization(client, monkeypatch):
    _stub_telephony(monkeypatch)
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    provider_id = _create_provider(client, org_a).json()["id"]

    write_headers = auth_headers(org_id=org_a, permissions=[permissions.CALLS_WRITE])
    client.post(
        "/calls",
        json={
            "to_number": "+15551234567",
            "telephony_provider_config_id": provider_id,
            "call_script": {"persona": "You are Ava.", "objective": "Confirm.", "fields": []},
            "max_conversation_duration_minutes": 5,
        },
        headers=write_headers,
    )

    other_org_headers = auth_headers(org_id=org_b, permissions=[permissions.CALLS_READ])
    response = client.get("/calls", headers=other_org_headers)
    assert response.json()["items"] == []
