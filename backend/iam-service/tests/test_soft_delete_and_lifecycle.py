"""Coverage for the enterprise-hardening pass: soft-delete on RoleDefinition/RoleAssignment,
Organization rename/deactivate/reactivate (and the login-rejection behavior that must follow
from deactivation), ServicePrincipal rename, and User.display_name edits.

The single most important test in this file is
`test_revoked_role_assignment_permissions_disappear_from_next_token` - it proves the actual
security-critical fix (permission_service.resolve_permissions filtering out revoked
assignments / archived role definitions), not just that the row gets a `revoked_at` timestamp.
"""
import jwt as pyjwt

from app.core.constants import ServiceName
from app.services.permission_service import resolve_permissions
from tests.helpers import add_membership, assign_org_role, assign_service_role, create_org, create_user, get_builtin_role


def _login(client, email, password="correct-horse-battery", organization_id=None):
    payload = {"email": email, "password": password}
    if organization_id:
        payload["organization_id"] = str(organization_id)
    resp = client.post("/auth/login", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _grant(db, user, org, role_name):
    role = get_builtin_role(db, role_name)
    assign_org_role(db, principal_type="user", principal_id=user.id, role_definition_id=role.id, organization_id=org.id)


# --- Organization rename / deactivate / reactivate -------------------------------------------------


def test_rename_organization(client, db):
    org = create_org(db)
    owner = create_user(db, "org-owner@example.com")
    add_membership(db, owner, org)
    _grant(db, owner, org, "Organization Owner")
    token = _login(client, "org-owner@example.com")

    resp = client.patch(f"/organizations/{org.id}", json={"name": "Renamed Corp"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Renamed Corp"


def test_rename_organization_requires_permission(client, db):
    org = create_org(db)
    user = create_user(db, "no-perm@example.com")
    add_membership(db, user, org)
    token = _login(client, "no-perm@example.com")

    resp = client.patch(f"/organizations/{org.id}", json={"name": "Nope"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_deactivate_organization_rejects_future_logins(client, db):
    org = create_org(db)
    owner = create_user(db, "deactivate-owner@example.com")
    member = create_user(db, "deactivate-member@example.com")
    add_membership(db, owner, org)
    add_membership(db, member, org)
    _grant(db, owner, org, "Organization Owner")

    owner_token = _login(client, "deactivate-owner@example.com")

    # Member can log in fine before deactivation.
    _login(client, "deactivate-member@example.com")

    resp = client.post(f"/organizations/{org.id}/deactivate", headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    denied = client.post("/auth/login", json={"email": "deactivate-member@example.com", "password": "correct-horse-battery"})
    assert denied.status_code == 403

    # Reactivating restores login.
    resp = client.post(f"/organizations/{org.id}/reactivate", headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True
    _login(client, "deactivate-member@example.com")


# --- RoleDefinition archive (soft delete) ------------------------------------------------------


def test_archive_role_definition_is_soft_and_excluded_by_default(client, db):
    org = create_org(db)
    admin = create_user(db, "role-admin@example.com")
    add_membership(db, admin, org)
    _grant(db, admin, org, "Organization Owner")
    token = _login(client, "role-admin@example.com")

    created = client.post(
        "/role-definitions",
        json={"organization_id": str(org.id), "name": "Temp Role", "permission_codes": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 201
    role_id = created.json()["id"]

    archived = client.delete(f"/role-definitions/{role_id}", headers={"Authorization": f"Bearer {token}"})
    assert archived.status_code == 204

    listed = client.get("/role-definitions", params={"organization_id": str(org.id)}, headers={"Authorization": f"Bearer {token}"})
    assert all(r["id"] != role_id for r in listed.json())

    listed_incl = client.get(
        "/role-definitions",
        params={"organization_id": str(org.id), "include_archived": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    match = next(r for r in listed_incl.json() if r["id"] == role_id)
    assert match["archived_at"] is not None


def test_cannot_assign_archived_role(client, db):
    org = create_org(db)
    admin = create_user(db, "archive-assign-admin@example.com")
    target = create_user(db, "archive-assign-target@example.com")
    add_membership(db, admin, org)
    add_membership(db, target, org)
    _grant(db, admin, org, "Organization Owner")
    token = _login(client, "archive-assign-admin@example.com")

    created = client.post(
        "/role-definitions",
        json={"organization_id": str(org.id), "name": "Soon Archived", "permission_codes": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    role_id = created.json()["id"]
    client.delete(f"/role-definitions/{role_id}", headers={"Authorization": f"Bearer {token}"})

    resp = client.post(
        "/role-assignments",
        json={
            "principal_type": "user",
            "principal_id": str(target.id),
            "role_definition_id": role_id,
            "organization_id": str(org.id),
            "scope_type": "organization",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_archived_role_definition_cannot_be_edited(client, db):
    org = create_org(db)
    admin = create_user(db, "archive-edit-admin@example.com")
    add_membership(db, admin, org)
    _grant(db, admin, org, "Organization Owner")
    token = _login(client, "archive-edit-admin@example.com")

    created = client.post(
        "/role-definitions",
        json={"organization_id": str(org.id), "name": "Edit Me Later", "permission_codes": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    role_id = created.json()["id"]
    client.delete(f"/role-definitions/{role_id}", headers={"Authorization": f"Bearer {token}"})

    resp = client.patch(f"/role-definitions/{role_id}", json={"name": "Nope"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


# --- RoleAssignment revoke (soft delete) - the security-critical one --------------------------------


def test_revoke_role_assignment_is_soft_delete(db):
    org = create_org(db)
    user = create_user(db, "revoke-soft@example.com")
    role = get_builtin_role(db, "Viewer")
    assignment = assign_org_role(db, principal_type="user", principal_id=user.id, role_definition_id=role.id, organization_id=org.id)

    from app.services.role_assignment_service import list_role_assignments, revoke_role_assignment

    revoke_role_assignment(db, assignment.id)
    db.expire_all()

    assert assignment.revoked_at is not None
    # Row still exists - soft delete, not a hard delete.
    assert db.get(type(assignment), assignment.id) is not None

    active_only = list_role_assignments(db, org.id)
    assert all(a.id != assignment.id for a in active_only)
    with_revoked = list_role_assignments(db, org.id, include_revoked=True)
    assert any(a.id == assignment.id for a in with_revoked)


def test_revoked_role_assignment_permissions_disappear_from_next_token(client, db):
    """The one correctness-critical assertion in this whole hardening pass: once a
    RoleAssignment is revoked, resolve_permissions (and therefore every freshly-issued access
    token) must stop including its permissions - immediately, not just once the row eventually
    gets cleaned up."""
    org = create_org(db)
    user = create_user(db, "revoke-e2e@example.com", "correct-horse-battery")
    add_membership(db, user, org)
    role = get_builtin_role(db, "Requirements Manager")
    assignment = assign_org_role(
        db, principal_type="user", principal_id=user.id, role_definition_id=role.id, organization_id=org.id
    )

    # Before revocation: permission is resolved and present on a real access token.
    perms_before = resolve_permissions(db, principal_type="user", principal_id=user.id, organization_id=org.id)
    assert "talentos.intake.requirements.delete" in perms_before

    token_before = _login(client, "revoke-e2e@example.com")
    claims_before = pyjwt.decode(token_before, options={"verify_signature": False})
    assert "talentos.intake.requirements.delete" in claims_before["permissions"]

    # Revoke via the real HTTP endpoint (as an org owner would), then verify at both layers.
    owner = create_user(db, "revoke-e2e-owner@example.com")
    add_membership(db, owner, org)
    _grant(db, owner, org, "Organization Owner")
    owner_token = _login(client, "revoke-e2e-owner@example.com")

    revoke_resp = client.delete(f"/role-assignments/{assignment.id}", headers={"Authorization": f"Bearer {owner_token}"})
    assert revoke_resp.status_code == 204

    perms_after = resolve_permissions(db, principal_type="user", principal_id=user.id, organization_id=org.id)
    assert "talentos.intake.requirements.delete" not in perms_after
    assert perms_after == []

    token_after = _login(client, "revoke-e2e@example.com")
    claims_after = pyjwt.decode(token_after, options={"verify_signature": False})
    assert "talentos.intake.requirements.delete" not in claims_after["permissions"]


def test_resolve_permissions_ignores_archived_role_definition_even_if_assignment_active(db):
    org = create_org(db)
    user = create_user(db, "archived-role-perm@example.com")
    role = get_builtin_role(db, "Viewer")
    assign_org_role(db, principal_type="user", principal_id=user.id, role_definition_id=role.id, organization_id=org.id)

    perms = resolve_permissions(db, principal_type="user", principal_id=user.id, organization_id=org.id)
    assert "talentos.intake.requirements.read" in perms

    # Built-in roles can't be archived via the API, so archive it directly to isolate the
    # resolve_permissions filter itself from the archive-endpoint's is_builtin guard.
    from datetime import datetime, timezone

    role.archived_at = datetime.now(timezone.utc)
    db.commit()

    perms_after = resolve_permissions(db, principal_type="user", principal_id=user.id, organization_id=org.id)
    assert "talentos.intake.requirements.read" not in perms_after


# --- ServicePrincipal rename --------------------------------------------------------------------


def test_rename_service_principal(client, db):
    org = create_org(db)
    admin = create_user(db, "sp-rename-admin@example.com")
    add_membership(db, admin, org)
    _grant(db, admin, org, "Organization Owner")
    token = _login(client, "sp-rename-admin@example.com")

    created = client.post(
        "/service-principals",
        json={"name": "Old Name", "organization_id": str(org.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 201
    sp_id = created.json()["service_principal"]["id"]

    renamed = client.patch(f"/service-principals/{sp_id}", json={"name": "New Name"}, headers={"Authorization": f"Bearer {token}"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "New Name"
    assert renamed.json()["client_id"] == created.json()["service_principal"]["client_id"]


# --- User display_name edit ----------------------------------------------------------------------


def test_update_user_display_name(client, db):
    org = create_org(db)
    admin = create_user(db, "name-edit-admin@example.com")
    member = create_user(db, "name-edit-target@example.com")
    add_membership(db, admin, org)
    add_membership(db, member, org)
    _grant(db, admin, org, "Organization Owner")
    token = _login(client, "name-edit-admin@example.com")

    resp = client.patch(
        f"/organizations/{org.id}/users/{member.id}",
        json={"display_name": "New Display Name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["display_name"] == "New Display Name"

    listed = client.get(f"/organizations/{org.id}/users", headers={"Authorization": f"Bearer {token}"})
    match = next(u for u in listed.json() if u["user_id"] == str(member.id))
    assert match["display_name"] == "New Display Name"
