"""The platform superadmin tier, per-organization entitlement ceilings, and the unified
invite / forgot-password flow.

The two load-bearing tests here are:

  * `test_a_permission_outside_the_ceiling_never_reaches_a_token` - proves the entitlement
    ceiling is actually enforced where it matters (permission_service.resolve_permissions),
    not merely stored. Deliberately mirrors
    test_revoked_role_assignment_permissions_disappear_from_next_token in style.
  * `test_every_iam_permission_still_is_not_superadmin` - proves the superadmin tier is a
    genuinely separate axis rather than a very powerful permission.
"""
import jwt as pyjwt
from sqlalchemy import select

from app.core.password import hash_password
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.services.permission_service import resolve_permissions
from tests.helpers import add_membership, assign_org_role, create_org, create_user, get_builtin_role

PASSWORD = "correct-horse-battery"
NEW_PASSWORD = "brand-new-passphrase-1"


def _login(client, email, password=PASSWORD, organization_id=None):
    payload = {"email": email, "password": password}
    if organization_id:
        payload["organization_id"] = str(organization_id)
    return client.post("/auth/login", json=payload)


def _claims(token):
    return pyjwt.decode(token, options={"verify_signature": False})


def create_superadmin(db, email="superadmin@example.com") -> User:
    """A superadmin is a user with the flag and NO organization membership - the absence is the
    point, so this helper deliberately does not add one."""
    user = User(
        email=email,
        password_hash=hash_password(PASSWORD),
        display_name="Platform Superadmin",
        status="active",
        is_superadmin=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _superadmin_token(client, db, email="superadmin@example.com") -> str:
    create_superadmin(db, email)
    response = _login(client, email)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


# --- The superadmin tier ---------------------------------------------------------------------


def test_a_superadmin_with_no_organization_membership_can_log_in(client, db):
    create_superadmin(db)
    response = _login(client, "superadmin@example.com")
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["organization_id"] is None
    claims = _claims(body["access_token"])
    assert claims["org_id"] is None
    assert claims["permissions"] == []
    assert claims["is_superadmin"] is True


def test_an_ordinary_user_with_no_membership_still_cannot_log_in(client, db):
    """The superadmin branch in login must not have loosened the rule for everyone else."""
    create_user(db, "orphan@example.com")
    response = _login(client, "orphan@example.com")
    assert response.status_code == 403


def test_a_superadmin_who_does_belong_to_an_org_keeps_the_normal_org_scoped_flow(client, db):
    superadmin = create_superadmin(db)
    org = create_org(db)
    add_membership(db, superadmin, org)
    assign_org_role(
        db,
        principal_type="user",
        principal_id=superadmin.id,
        role_definition_id=get_builtin_role(db, "Viewer").id,
        organization_id=org.id,
    )

    body = _login(client, "superadmin@example.com").json()
    claims = _claims(body["access_token"])
    assert claims["org_id"] == str(org.id)
    assert claims["is_superadmin"] is True
    assert "talentos.intake.applicants.read" in claims["permissions"]


def test_every_iam_permission_still_is_not_superadmin(client, db):
    """The security-critical separation: Organization Owner holds every talentos.iam.*
    permission there is, and is still refused by a require_superadmin endpoint."""
    org = create_org(db)
    owner = create_user(db, "owner@example.com")
    add_membership(db, owner, org)
    assign_org_role(
        db,
        principal_type="user",
        principal_id=owner.id,
        role_definition_id=get_builtin_role(db, "Organization Owner").id,
        organization_id=org.id,
    )
    token = _login(client, "owner@example.com").json()["access_token"]
    claims = _claims(token)
    assert "talentos.iam.organizations.manage" in claims["permissions"]
    assert claims["is_superadmin"] is False

    response = client.post(
        "/organizations",
        json={
            "name": "Sneaky Org",
            "admin_email": "sneaky@example.com",
            "allowed_permission_codes": ["talentos.intake.applicants.read"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert "superadmin" in response.json()["detail"].lower()


def test_a_superadmin_sees_every_organization_while_a_member_sees_only_theirs(client, db):
    org_a = create_org(db, "Org A")
    create_org(db, "Org B")
    member = create_user(db, "member@example.com")
    add_membership(db, member, org_a)

    superadmin_token = _superadmin_token(client, db)
    all_orgs = client.get("/organizations", headers={"Authorization": f"Bearer {superadmin_token}"}).json()
    assert {org["name"] for org in all_orgs} >= {"Org A", "Org B"}

    member_token = _login(client, "member@example.com").json()["access_token"]
    mine = client.get("/organizations", headers={"Authorization": f"Bearer {member_token}"}).json()
    assert [org["name"] for org in mine] == ["Org A"]


# --- Combined organization + admin provisioning ------------------------------------------------


def test_creating_an_organization_provisions_its_admin_role_and_invite(client, db):
    token = _superadmin_token(client, db)
    codes = ["talentos.iam.users.invite", "talentos.iam.users.manage", "talentos.intake.applicants.read"]

    response = client.post(
        "/organizations",
        json={
            "name": "Acme Inc",
            "admin_email": "Dana@AcmeInc.com",
            "admin_display_name": "Dana Admin",
            "allowed_permission_codes": codes,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["organization"]["name"] == "Acme Inc"
    assert sorted(body["organization"]["allowed_permissions"]) == sorted(codes)

    # The admin exists, is invited (no usable password yet), and email was normalized.
    assert body["admin"]["email"] == "dana@acmeinc.com"
    assert body["admin"]["status"] == "invited"
    admin = db.execute(select(User).where(User.email == "dana@acmeinc.com")).scalar_one()
    assert admin.password_hash is None

    # ...and holds the Organization Admin role, intersected down to the ceiling.
    permissions = resolve_permissions(
        db, principal_type="user", principal_id=admin.id, organization_id=body["organization"]["id"]
    )
    assert sorted(permissions) == sorted(codes)

    # ...and has exactly one single-use invite token waiting.
    tokens = db.execute(select(PasswordResetToken).where(PasswordResetToken.user_id == admin.id)).scalars().all()
    assert len(tokens) == 1
    assert tokens[0].used_at is None


def test_creating_an_organization_requires_at_least_one_permission_code(client, db):
    token = _superadmin_token(client, db)
    response = client.post(
        "/organizations",
        json={"name": "Empty Org", "admin_email": "nobody@example.com", "allowed_permission_codes": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_an_unknown_permission_code_is_rejected_rather_than_silently_stored(client, db):
    token = _superadmin_token(client, db)
    response = client.post(
        "/organizations",
        json={
            "name": "Typo Org",
            "admin_email": "nobody@example.com",
            "allowed_permission_codes": ["talentos.iam.usres.invite"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    assert "talentos.iam.usres.invite" in response.json()["detail"]


# --- Entitlement ceilings ----------------------------------------------------------------------


def test_a_permission_outside_the_ceiling_never_reaches_a_token(client, db):
    """THE test for entitlements. An organization is capped to a small set; a role granting
    something outside that set is assigned anyway; the freshly-issued token must not carry it.

    Enforcement lives in resolve_permissions, which runs on every token issuance - so this holds
    regardless of how the role was authored or assigned, and needs no role rewriting."""
    org = create_org(db, "Capped Org")
    org.allowed_permissions = ["talentos.intake.applicants.read"]
    db.commit()

    user = create_user(db, "capped@example.com")
    add_membership(db, user, org)
    # Organization Owner grants everything - far beyond the ceiling.
    assign_org_role(
        db,
        principal_type="user",
        principal_id=user.id,
        role_definition_id=get_builtin_role(db, "Organization Owner").id,
        organization_id=org.id,
    )

    claims = _claims(_login(client, "capped@example.com").json()["access_token"])
    assert claims["permissions"] == ["talentos.intake.applicants.read"]
    assert "talentos.iam.organizations.manage" not in claims["permissions"]
    assert "talentos.intake.applicants.write" not in claims["permissions"]


def test_an_organization_with_no_ceiling_is_unrestricted(client, db):
    """Backward compatibility: NULL allowed_permissions must mean unrestricted, not locked out."""
    org = create_org(db, "Legacy Org")
    assert org.allowed_permissions is None
    user = create_user(db, "legacy@example.com")
    add_membership(db, user, org)
    assign_org_role(
        db,
        principal_type="user",
        principal_id=user.id,
        role_definition_id=get_builtin_role(db, "Organization Owner").id,
        organization_id=org.id,
    )

    claims = _claims(_login(client, "legacy@example.com").json()["access_token"])
    assert "talentos.iam.organizations.manage" in claims["permissions"]


def test_lowering_a_ceiling_takes_effect_on_the_very_next_token(client, db):
    org = create_org(db, "Shrinking Org")
    user = create_user(db, "shrink@example.com")
    add_membership(db, user, org)
    assign_org_role(
        db,
        principal_type="user",
        principal_id=user.id,
        role_definition_id=get_builtin_role(db, "Viewer").id,
        organization_id=org.id,
    )
    before = _claims(_login(client, "shrink@example.com").json()["access_token"])["permissions"]
    assert "talentos.intake.applicants.read" in before
    assert "talentos.intake.requirements.read" in before

    superadmin_token = _superadmin_token(client, db)
    response = client.patch(
        f"/organizations/{org.id}/entitlements",
        json={"allowed_permission_codes": ["talentos.intake.applicants.read"]},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert response.status_code == 200, response.text

    after = _claims(_login(client, "shrink@example.com").json()["access_token"])["permissions"]
    assert after == ["talentos.intake.applicants.read"]


def test_clearing_a_ceiling_restores_unrestricted(client, db):
    org = create_org(db, "Restored Org")
    org.allowed_permissions = ["talentos.intake.applicants.read"]
    db.commit()
    user = create_user(db, "restored@example.com")
    add_membership(db, user, org)
    assign_org_role(
        db,
        principal_type="user",
        principal_id=user.id,
        role_definition_id=get_builtin_role(db, "Viewer").id,
        organization_id=org.id,
    )

    superadmin_token = _superadmin_token(client, db)
    client.patch(
        f"/organizations/{org.id}/entitlements",
        json={"allowed_permission_codes": []},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )

    after = _claims(_login(client, "restored@example.com").json()["access_token"])["permissions"]
    assert len(after) > 1


def test_setting_entitlements_requires_superadmin_not_just_org_manage(client, db):
    org = create_org(db)
    owner = create_user(db, "owner2@example.com")
    add_membership(db, owner, org)
    assign_org_role(
        db,
        principal_type="user",
        principal_id=owner.id,
        role_definition_id=get_builtin_role(db, "Organization Owner").id,
        organization_id=org.id,
    )
    token = _login(client, "owner2@example.com").json()["access_token"]

    response = client.patch(
        f"/organizations/{org.id}/entitlements",
        json={"allowed_permission_codes": ["talentos.intake.applicants.read"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# --- Unified invite / first-login / forgot-password ---------------------------------------------


def test_an_invited_user_becomes_active_by_redeeming_the_invite_token(client, db):
    """One token type, one endpoint, both flows. An invite is redeemed through exactly the same
    POST /auth/password-reset/confirm a forgot-password link uses."""
    superadmin_token = _superadmin_token(client, db)
    created = client.post(
        "/organizations",
        json={
            "name": "Invite Org",
            "admin_email": "newadmin@example.com",
            "admin_display_name": "New Admin",
            "allowed_permission_codes": ["talentos.iam.users.manage"],
        },
        headers={"Authorization": f"Bearer {superadmin_token}"},
    ).json()

    admin = db.execute(select(User).where(User.email == "newadmin@example.com")).scalar_one()
    assert admin.status == "invited"

    # An invited user cannot log in yet - there is no password to present.
    assert _login(client, "newadmin@example.com", NEW_PASSWORD).status_code == 401

    token_row = db.execute(select(PasswordResetToken).where(PasswordResetToken.user_id == admin.id)).scalar_one()
    plain = _plaintext_for(db, token_row)

    response = client.post("/auth/password-reset/confirm", json={"token": plain, "new_password": NEW_PASSWORD})
    assert response.status_code == 204, response.text

    db.refresh(admin)
    assert admin.status == "active"
    assert admin.password_hash is not None

    login = _login(client, "newadmin@example.com", NEW_PASSWORD)
    assert login.status_code == 200, login.text
    assert login.json()["organization_id"] == created["organization"]["id"]


def test_an_invite_token_is_single_use(client, db):
    user = create_user(db, "single@example.com", status="invited")
    org = create_org(db)
    add_membership(db, user, org)
    plain = _issue_token(db, user)

    assert client.post("/auth/password-reset/confirm", json={"token": plain, "new_password": NEW_PASSWORD}).status_code == 204
    second = client.post("/auth/password-reset/confirm", json={"token": plain, "new_password": "another-passphrase-2"})
    assert second.status_code == 422


def test_forgot_password_issues_a_token_and_does_not_reveal_unknown_emails(client, db):
    org = create_org(db)
    user = create_user(db, "forgetful@example.com")
    add_membership(db, user, org)

    assert client.post("/auth/password-reset/request", json={"email": "forgetful@example.com"}).status_code == 202
    assert client.post("/auth/password-reset/request", json={"email": "nobody@example.com"}).status_code == 202

    tokens = db.execute(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)).scalars().all()
    assert len(tokens) == 1

    plain = _plaintext_for(db, tokens[0])
    assert client.post("/auth/password-reset/confirm", json={"token": plain, "new_password": NEW_PASSWORD}).status_code == 204
    assert _login(client, "forgetful@example.com", NEW_PASSWORD).status_code == 200


def test_inviting_a_user_into_an_org_creates_them_as_invited_with_a_token(client, db):
    org = create_org(db)
    inviter = create_user(db, "inviter@example.com")
    add_membership(db, inviter, org)
    assign_org_role(
        db,
        principal_type="user",
        principal_id=inviter.id,
        role_definition_id=get_builtin_role(db, "Organization Admin").id,
        organization_id=org.id,
    )
    token = _login(client, "inviter@example.com").json()["access_token"]

    response = client.post(
        f"/organizations/{org.id}/users",
        json={"email": "invitee@example.com", "display_name": "Invitee"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "invited"

    invitee = db.execute(select(User).where(User.email == "invitee@example.com")).scalar_one()
    tokens = db.execute(select(PasswordResetToken).where(PasswordResetToken.user_id == invitee.id)).scalars().all()
    assert len(tokens) == 1


# --- helpers ------------------------------------------------------------------------------------

# Tokens are stored only as a hash, so a test cannot read one back out of the database. These
# helpers re-mint through the service so the test holds the plaintext, which is exactly what the
# emailed link would have carried.


def _issue_token(db, user) -> str:
    from app.config import get_settings
    from app.services.password_reset_service import issue_reset_token

    return issue_reset_token(db, get_settings(), user)


def _plaintext_for(db, token_row) -> str:
    """Replace the stored hash with one for a known plaintext. Cleaner than reaching into the
    hashing internals from every test, and it exercises the same single-use/expiry columns."""
    from app.core.secrets import hash_secret

    plain = "test-plaintext-token-" + str(token_row.id)
    token_row.token_hash = hash_secret(plain)
    db.commit()
    return plain


def test_a_superadmin_can_scope_a_session_to_any_organization_without_membership(client, db):
    """Overseeing every tenant is the tier's purpose, and GET /organizations already lists them
    all - a switcher offering organizations they could not enter would be a dead end.

    Crucially this grants SCOPE, not authority: the resulting token still carries no org-scoped
    permissions, because they hold no role there."""
    org = create_org(db, "Someone Elses Org")
    token = _superadmin_token(client, db)

    response = client.post(
        "/auth/token/switch-org",
        json={"organization_id": str(org.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    claims = _claims(response.json()["access_token"])
    assert claims["org_id"] == str(org.id)
    assert claims["is_superadmin"] is True
    assert claims["permissions"] == []


def test_an_ordinary_user_still_cannot_switch_into_an_organization_they_do_not_belong_to(client, db):
    home = create_org(db, "Home Org")
    other = create_org(db, "Other Org")
    user = create_user(db, "switcher@example.com")
    add_membership(db, user, home)
    token = _login(client, "switcher@example.com").json()["access_token"]

    response = client.post(
        "/auth/token/switch-org",
        json={"organization_id": str(other.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_a_superadmin_cannot_switch_into_a_deactivated_organization(client, db):
    org = create_org(db, "Dormant Org")
    org.is_active = False
    db.commit()
    token = _superadmin_token(client, db)

    response = client.post(
        "/auth/token/switch-org",
        json={"organization_id": str(org.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_a_superadmin_can_rename_and_deactivate_any_organization(client, db):
    """The Organizations page shows a superadmin deactivate/reactivate controls for every tenant,
    so the endpoints behind them have to accept a principal with no org-scoped permissions."""
    org = create_org(db, "Someone Elses Org To Manage")
    token = _superadmin_token(client, db)
    headers = {"Authorization": f"Bearer {token}"}

    renamed = client.patch(f"/organizations/{org.id}", json={"name": "Renamed By Platform"}, headers=headers)
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Renamed By Platform"

    assert client.post(f"/organizations/{org.id}/deactivate", headers=headers).json()["is_active"] is False
    assert client.post(f"/organizations/{org.id}/reactivate", headers=headers).json()["is_active"] is True


def test_an_org_owner_can_still_manage_their_own_organizations_lifecycle(client, db):
    """Widening those endpoints for the platform tier must not have narrowed them for the tier
    that already had them."""
    org = create_org(db, "Self Managed Org")
    owner = create_user(db, "selfowner@example.com")
    add_membership(db, owner, org)
    assign_org_role(
        db,
        principal_type="user",
        principal_id=owner.id,
        role_definition_id=get_builtin_role(db, "Organization Owner").id,
        organization_id=org.id,
    )
    headers = {"Authorization": f"Bearer {_login(client, 'selfowner@example.com').json()['access_token']}"}

    assert client.patch(f"/organizations/{org.id}", json={"name": "Renamed By Owner"}, headers=headers).status_code == 200
    assert client.post(f"/organizations/{org.id}/deactivate", headers=headers).status_code == 200


def test_a_user_without_the_permission_still_cannot_touch_an_organizations_lifecycle(client, db):
    org = create_org(db, "Protected Org")
    viewer = create_user(db, "viewer@example.com")
    add_membership(db, viewer, org)
    assign_org_role(
        db,
        principal_type="user",
        principal_id=viewer.id,
        role_definition_id=get_builtin_role(db, "Viewer").id,
        organization_id=org.id,
    )
    headers = {"Authorization": f"Bearer {_login(client, 'viewer@example.com').json()['access_token']}"}

    assert client.patch(f"/organizations/{org.id}", json={"name": "Nope"}, headers=headers).status_code == 403
    assert client.post(f"/organizations/{org.id}/deactivate", headers=headers).status_code == 403


def test_a_superadmin_can_administer_a_tenant_it_holds_no_membership_in(client, db):
    """The capability that makes the tier complete rather than a trapdoor.

    Creating a tenant and its first admin is not enough on its own: if that admin leaves, someone
    has to be able to appoint a replacement. A superadmin holds no org-scoped permissions at all,
    so without require_permission honouring the flag they would be locked out of every tenant
    they created."""
    org = create_org(db, "Tenant Needing A New Admin")
    headers = {"Authorization": f"Bearer {_superadmin_token(client, db)}"}

    listed = client.get(f"/organizations/{org.id}/users", headers=headers)
    assert listed.status_code == 200, listed.text

    invited = client.post(
        f"/organizations/{org.id}/users",
        json={"email": "replacement-admin@example.com", "display_name": "Replacement Admin"},
        headers=headers,
    )
    assert invited.status_code == 201, invited.text

    # ...and can then actually make them an admin.
    assignment = client.post(
        "/role-assignments",
        json={
            "principal_type": "user",
            "principal_id": invited.json()["id"],
            "role_definition_id": str(get_builtin_role(db, "Organization Admin").id),
            "organization_id": str(org.id),
            "scope_type": "organization",
        },
        headers=headers,
    )
    assert assignment.status_code == 201, assignment.text

    assert client.get("/audit/events", params={"organization_id": str(org.id)}, headers=headers).status_code == 200
    assert client.get("/service-principals", params={"organization_id": str(org.id)}, headers=headers).status_code == 200


def test_the_superadmin_bypass_is_one_way(client, db):
    """A superadmin passes every permission check; no amount of permissions passes
    require_superadmin. Losing that asymmetry would silently promote every organization owner to
    the platform tier."""
    org = create_org(db, "One Way Org")
    owner = create_user(db, "oneway-owner@example.com")
    add_membership(db, owner, org)
    assign_org_role(
        db,
        principal_type="user",
        principal_id=owner.id,
        role_definition_id=get_builtin_role(db, "Organization Owner").id,
        organization_id=org.id,
    )
    owner_headers = {"Authorization": f"Bearer {_login(client, 'oneway-owner@example.com').json()['access_token']}"}

    # Holds every talentos.iam.* permission there is...
    assert client.get(f"/organizations/{org.id}/users", headers=owner_headers).status_code == 200
    # ...and still cannot reach a superadmin-only endpoint.
    assert client.patch(
        f"/organizations/{org.id}/entitlements",
        json={"allowed_permission_codes": ["talentos.iam.users.manage"]},
        headers=owner_headers,
    ).status_code == 403
