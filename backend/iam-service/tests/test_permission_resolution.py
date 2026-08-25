import jwt as pyjwt

from app.core.constants import ServiceName
from app.services.permission_service import resolve_permissions
from tests.helpers import add_membership, assign_org_role, assign_service_role, create_org, create_user, get_builtin_role


def test_resolve_permissions_org_scope_only(db):
    org = create_org(db)
    user = create_user(db, "org-scope@example.com")
    role = get_builtin_role(db, "Recruiter")
    assign_org_role(db, principal_type="user", principal_id=user.id, role_definition_id=role.id, organization_id=org.id)

    perms = set(resolve_permissions(db, principal_type="user", principal_id=user.id, organization_id=org.id))
    assert "talentos.intake.requirements.read" in perms
    assert "talentos.intake.requirements.write" in perms
    assert "talentos.intake.requirements.delete" not in perms  # Recruiter has no delete


def test_resolve_permissions_unions_org_and_service_scope(db):
    org = create_org(db)
    user = create_user(db, "union@example.com")
    viewer_role = get_builtin_role(db, "Viewer")
    agent_admin_role = get_builtin_role(db, "Agent Builder Admin")

    # Org-wide Viewer...
    assign_org_role(
        db, principal_type="user", principal_id=user.id, role_definition_id=viewer_role.id, organization_id=org.id
    )
    # ...plus Agent Builder Admin scoped only to the agent-builder service.
    assign_service_role(
        db,
        principal_type="user",
        principal_id=user.id,
        role_definition_id=agent_admin_role.id,
        organization_id=org.id,
        service_name=ServiceName.AGENT_BUILDER,
    )

    perms = set(resolve_permissions(db, principal_type="user", principal_id=user.id, organization_id=org.id))
    # From Viewer (org scope)
    assert "talentos.intake.requirements.read" in perms
    # From Agent Builder Admin (service scope)
    assert "talentos.agentbuilder.models.manage" in perms
    assert "talentos.agentbuilder.agents.publish" in perms


def test_resolve_permissions_scoped_to_other_org_not_leaked(db):
    org_a = create_org(db, "Org A")
    org_b = create_org(db, "Org B")
    user = create_user(db, "isolated@example.com")
    owner_role = get_builtin_role(db, "Organization Owner")
    assign_org_role(
        db, principal_type="user", principal_id=user.id, role_definition_id=owner_role.id, organization_id=org_a.id
    )

    perms_in_b = resolve_permissions(db, principal_type="user", principal_id=user.id, organization_id=org_b.id)
    assert perms_in_b == []


def test_login_access_token_carries_resolved_permissions(client, db):
    from tests.helpers import add_membership

    org = create_org(db)
    user = create_user(db, "claims@example.com", "correct-horse-battery")
    add_membership(db, user, org)
    role = get_builtin_role(db, "Requirements Manager")
    assign_org_role(db, principal_type="user", principal_id=user.id, role_definition_id=role.id, organization_id=org.id)

    resp = client.post("/auth/login", json={"email": "claims@example.com", "password": "correct-horse-battery"})
    assert resp.status_code == 200
    access_token = resp.json()["access_token"]
    claims = pyjwt.decode(access_token, options={"verify_signature": False})

    assert claims["principal_type"] == "user"
    assert claims["email"] == "claims@example.com"
    assert claims["org_id"] == str(org.id)
    assert "talentos.intake.requirements.delete" in claims["permissions"]
    assert set(["sub", "iat", "exp", "jti"]).issubset(claims.keys())
