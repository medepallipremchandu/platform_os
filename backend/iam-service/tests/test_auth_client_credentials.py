from app.services.service_principal_service import create_service_principal, revoke_service_principal
from tests.helpers import assign_org_role, create_org, get_builtin_role


def test_client_credentials_grant_success(client, db):
    org = create_org(db)
    sp, secret = create_service_principal(db, organization_id=org.id, name="agent-builder svc", resource_type=None, resource_id=None)
    role = get_builtin_role(db, "Agent Builder Admin")
    assign_org_role(db, principal_type="service_principal", principal_id=sp.id, role_definition_id=role.id, organization_id=org.id)

    resp = client.post("/auth/token", json={"client_id": sp.client_id, "client_secret": secret})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert "refresh_token" not in body
    assert body["access_token"]


def test_client_credentials_wrong_secret(client, db):
    org = create_org(db)
    sp, _secret = create_service_principal(db, organization_id=org.id, name="svc", resource_type=None, resource_id=None)
    resp = client.post("/auth/token", json={"client_id": sp.client_id, "client_secret": "wrong-secret"})
    assert resp.status_code == 401


def test_client_credentials_revoked_rejected(client, db):
    org = create_org(db)
    sp, secret = create_service_principal(db, organization_id=org.id, name="svc", resource_type=None, resource_id=None)
    revoke_service_principal(db, sp.id)

    resp = client.post("/auth/token", json={"client_id": sp.client_id, "client_secret": secret})
    assert resp.status_code == 401


def test_client_credentials_resource_bound_scope(client, db):
    org = create_org(db)
    sp, secret = create_service_principal(
        db, organization_id=org.id, name="agent-42-invoke", resource_type="agent", resource_id="agent-42"
    )
    resp = client.post("/auth/token", json={"client_id": sp.client_id, "client_secret": secret})
    assert resp.status_code == 200

    import jwt as pyjwt

    claims = pyjwt.decode(resp.json()["access_token"], options={"verify_signature": False})
    assert claims["resource_scope"] == {"type": "agent", "id": "agent-42"}
    assert claims["name"] == "agent-42-invoke"
