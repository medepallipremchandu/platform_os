"""End-to-end: a caller without the required permission is denied (403), then - once granted
the role that carries that permission and re-authenticating (permissions are resolved and
embedded at token-issue time, design doc §5) - the same call succeeds."""
from tests.helpers import add_membership, assign_org_role, create_org, create_user, get_builtin_role


def _login(client, email, password="correct-horse-battery"):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_denial_then_grant_role_definitions_manage(client, db):
    org = create_org(db)
    user = create_user(db, "grace@example.com", "correct-horse-battery")
    add_membership(db, user, org)

    token = _login(client, "grace@example.com")
    create_payload = {
        "organization_id": str(org.id),
        "name": "Custom Role",
        "description": "test",
        "permission_codes": ["talentos.intake.requirements.read"],
    }

    denied = client.post(
        "/role-definitions", json=create_payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert denied.status_code == 403

    admin_role = get_builtin_role(db, "Organization Admin")
    assign_org_role(
        db, principal_type="user", principal_id=user.id, role_definition_id=admin_role.id, organization_id=org.id
    )

    new_token = _login(client, "grace@example.com")
    granted = client.post(
        "/role-definitions", json=create_payload, headers={"Authorization": f"Bearer {new_token}"}
    )
    assert granted.status_code == 201
    assert granted.json()["name"] == "Custom Role"


def test_builtin_role_cannot_be_edited_or_deleted(client, db):
    org = create_org(db)
    user = create_user(db, "heidi@example.com", "correct-horse-battery")
    add_membership(db, user, org)
    owner_role = get_builtin_role(db, "Organization Owner")
    assign_org_role(
        db, principal_type="user", principal_id=user.id, role_definition_id=owner_role.id, organization_id=org.id
    )
    token = _login(client, "heidi@example.com")

    resp = client.patch(
        f"/role-definitions/{owner_role.id}",
        json={"name": "Hacked"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403

    resp = client.delete(f"/role-definitions/{owner_role.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_missing_bearer_token_rejected(client):
    # GET /role-definitions has no specific permission gate in this build (any authenticated
    # caller may list roles), but it still requires *some* valid token.
    resp = client.get("/role-definitions", params={"organization_id": "00000000-0000-0000-0000-000000000000"})
    assert resp.status_code == 401

    resp2 = client.post("/role-definitions", json={"organization_id": "00000000-0000-0000-0000-000000000000", "name": "x"})
    assert resp2.status_code == 401
