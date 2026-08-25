import uuid

from app.core import permissions
from tests.conftest import auth_headers


def _create_provider(client, org_id, email="creator@example.com", **overrides):
    payload = {
        "name": "Acme Twilio",
        "provider": "twilio",
        "phone_number": "+15550001111",
        "credentials": {"accountSid": "ACxxxx", "authToken": "secret-token-value", "fromNumber": "+15550001111"},
        "visibility": "organization",
        "grant_user_ids": [],
    }
    payload.update(overrides)
    headers = auth_headers(org_id=org_id, permissions=[permissions.PROVIDERS_MANAGE], email=email)
    return client.post("/providers", json=payload, headers=headers)


def test_create_provider_round_trips_without_credentials(client):
    org_id = uuid.uuid4()
    response = _create_provider(client, org_id)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Acme Twilio"
    assert body["provider"] == "twilio"
    assert "credentials" not in body
    assert "encrypted_credentials" not in body
    assert body["created_by"] == "creator@example.com"

    list_headers = auth_headers(org_id=org_id, permissions=[permissions.PROVIDERS_READ])
    list_response = client.get("/providers", headers=list_headers)
    assert list_response.status_code == 200
    listed = list_response.json()["items"]
    assert len(listed) == 1
    assert "credentials" not in listed[0]
    assert "encrypted_credentials" not in listed[0]


def test_provider_scoped_to_organization(client):
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    _create_provider(client, org_a)

    headers_b = auth_headers(org_id=org_b, permissions=[permissions.PROVIDERS_READ])
    response = client.get("/providers", headers=headers_b)
    assert response.json()["items"] == []


def test_revoke_provider_removes_it_from_list(client):
    org_id = uuid.uuid4()
    create_response = _create_provider(client, org_id)
    provider_id = create_response.json()["id"]

    manage_headers = auth_headers(org_id=org_id, permissions=[permissions.PROVIDERS_MANAGE])
    revoke_response = client.delete(f"/providers/{provider_id}", headers=manage_headers)
    assert revoke_response.status_code == 200
    assert revoke_response.json()["revoked_at"] is not None

    read_headers = auth_headers(org_id=org_id, permissions=[permissions.PROVIDERS_READ])
    list_response = client.get("/providers", headers=read_headers)
    assert list_response.json()["items"] == []


def test_update_provider_renames_and_updates_phone_without_leaking_credentials(client):
    org_id = uuid.uuid4()
    create_response = _create_provider(client, org_id)
    provider_id = create_response.json()["id"]

    manage_headers = auth_headers(org_id=org_id, permissions=[permissions.PROVIDERS_MANAGE])
    update_response = client.patch(
        f"/providers/{provider_id}",
        json={"name": "Renamed Twilio", "phone_number": "+15559998888"},
        headers=manage_headers,
    )
    assert update_response.status_code == 200
    body = update_response.json()
    assert body["name"] == "Renamed Twilio"
    assert body["phone_number"] == "+15559998888"
    assert "credentials" not in body
    assert "encrypted_credentials" not in body

    # Stored credentials are untouched when the PATCH omits `credentials`.
    from app.core.crypto import decrypt_credentials
    from app.database import SessionLocal
    from app.models.telephony_provider import TelephonyProviderConfig

    db = SessionLocal()
    try:
        config = db.get(TelephonyProviderConfig, uuid.UUID(provider_id))
        decrypted = decrypt_credentials(config.encrypted_credentials)
        assert decrypted["authToken"] == "secret-token-value"  # unchanged from _create_provider's default payload
    finally:
        db.close()


def test_update_provider_can_replace_credentials(client):
    org_id = uuid.uuid4()
    create_response = _create_provider(client, org_id)
    provider_id = create_response.json()["id"]

    manage_headers = auth_headers(org_id=org_id, permissions=[permissions.PROVIDERS_MANAGE])
    update_response = client.patch(
        f"/providers/{provider_id}",
        json={"credentials": {"accountSid": "ACnew", "authToken": "new-secret", "fromNumber": "+15550001111"}},
        headers=manage_headers,
    )
    assert update_response.status_code == 200
    body = update_response.json()
    assert "credentials" not in body
    assert "encrypted_credentials" not in body

    from app.core.crypto import decrypt_credentials
    from app.database import SessionLocal
    from app.models.telephony_provider import TelephonyProviderConfig

    db = SessionLocal()
    try:
        config = db.get(TelephonyProviderConfig, uuid.UUID(provider_id))
        decrypted = decrypt_credentials(config.encrypted_credentials)
        assert decrypted["authToken"] == "new-secret"
    finally:
        db.close()


def test_update_provider_requires_manage_permission(client):
    org_id = uuid.uuid4()
    create_response = _create_provider(client, org_id)
    provider_id = create_response.json()["id"]

    read_only_headers = auth_headers(org_id=org_id, permissions=[permissions.PROVIDERS_READ])
    response = client.patch(f"/providers/{provider_id}", json={"name": "Nope"}, headers=read_only_headers)
    assert response.status_code == 403


def test_list_providers_hides_revoked_unless_include_revoked(client):
    org_id = uuid.uuid4()
    create_response = _create_provider(client, org_id)
    provider_id = create_response.json()["id"]

    manage_headers = auth_headers(org_id=org_id, permissions=[permissions.PROVIDERS_MANAGE])
    client.delete(f"/providers/{provider_id}", headers=manage_headers)

    read_headers = auth_headers(org_id=org_id, permissions=[permissions.PROVIDERS_READ])
    default_list = client.get("/providers", headers=read_headers)
    assert default_list.json()["items"] == []

    with_revoked = client.get("/providers", params={"include_revoked": "true"}, headers=read_headers)
    items = with_revoked.json()["items"]
    assert len(items) == 1
    assert items[0]["revoked_at"] is not None


def test_restricted_provider_hidden_from_other_user_until_granted(client):
    org_id = uuid.uuid4()
    creator_headers = auth_headers(org_id=org_id, permissions=[permissions.PROVIDERS_MANAGE], email="alice@example.com")
    create_response = client.post(
        "/providers",
        json={
            "name": "Restricted Twilio",
            "provider": "twilio",
            "phone_number": "+15550002222",
            "credentials": {"accountSid": "ACyyyy", "authToken": "secret2", "fromNumber": "+15550002222"},
            "visibility": "restricted",
            "grant_user_ids": [],
        },
        headers=creator_headers,
    )
    assert create_response.status_code == 201
    provider_id = create_response.json()["id"]

    # Bob (a different user in the same org) can't see it yet.
    bob_headers = auth_headers(org_id=org_id, permissions=[permissions.PROVIDERS_READ], email="bob@example.com")
    bob_list = client.get("/providers", headers=bob_headers)
    assert bob_list.json()["items"] == []

    # The creator can always see their own restricted resource.
    alice_read_headers = auth_headers(org_id=org_id, permissions=[permissions.PROVIDERS_READ], email="alice@example.com")
    alice_list = client.get("/providers", headers=alice_read_headers)
    assert len(alice_list.json()["items"]) == 1

    # A service-principal caller sees every org-scoped resource regardless of visibility.
    service_headers = auth_headers(
        org_id=org_id, permissions=[permissions.PROVIDERS_READ], principal_type="service_principal", email=None, sub="svc-1"
    )
    service_list = client.get("/providers", headers=service_headers)
    assert len(service_list.json()["items"]) == 1

    # Grant Bob access directly via the service layer (no PATCH /providers endpoint - grants are
    # only settable at creation time per the API surface), then confirm he can see it now.
    from app.database import SessionLocal
    from app.models.telephony_provider import TelephonyProviderConfigGrant

    db = SessionLocal()
    try:
        db.add(TelephonyProviderConfigGrant(provider_config_id=uuid.UUID(provider_id), user_id="bob@example.com"))
        db.commit()
    finally:
        db.close()

    bob_list_after_grant = client.get("/providers", headers=bob_headers)
    assert len(bob_list_after_grant.json()["items"]) == 1
