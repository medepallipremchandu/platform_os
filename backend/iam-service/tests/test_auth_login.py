from app.config import get_settings
from tests.helpers import add_membership, assign_org_role, create_org, create_user, get_builtin_role


def test_login_success(client, db):
    org = create_org(db)
    user = create_user(db, "alice@example.com", "correct-horse-battery")
    add_membership(db, user, org)
    role = get_builtin_role(db, "Viewer")
    assign_org_role(db, principal_type="user", principal_id=user.id, role_definition_id=role.id, organization_id=org.id)

    response = client.post("/auth/login", json={"email": "alice@example.com", "password": "correct-horse-battery"})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["organization_id"] == str(org.id)
    assert body["expires_in"] == get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert body["access_token"]
    assert body["refresh_token"]


def test_login_wrong_password(client, db):
    org = create_org(db)
    user = create_user(db, "bob@example.com", "correct-horse-battery")
    add_membership(db, user, org)

    response = client.post("/auth/login", json={"email": "bob@example.com", "password": "wrong-password"})
    assert response.status_code == 401


def test_login_unknown_email(client):
    response = client.post("/auth/login", json={"email": "nobody@example.com", "password": "whatever12345"})
    assert response.status_code == 401


def test_login_lockout_after_threshold(client, db):
    org = create_org(db)
    user = create_user(db, "carol@example.com", "correct-horse-battery")
    add_membership(db, user, org)
    settings = get_settings()

    last_response = None
    for _ in range(settings.LOGIN_LOCKOUT_THRESHOLD):
        last_response = client.post("/auth/login", json={"email": "carol@example.com", "password": "wrong"})

    # The attempt that crosses the threshold locks the account.
    assert last_response.status_code == 423

    # Even the correct password is now rejected while locked.
    response = client.post("/auth/login", json={"email": "carol@example.com", "password": "correct-horse-battery"})
    assert response.status_code == 423


def test_login_multiple_orgs_requires_organization_id(client, db):
    org_a = create_org(db, "Org A")
    org_b = create_org(db, "Org B")
    user = create_user(db, "dave@example.com", "correct-horse-battery")
    add_membership(db, user, org_a)
    add_membership(db, user, org_b)

    response = client.post("/auth/login", json={"email": "dave@example.com", "password": "correct-horse-battery"})
    assert response.status_code == 409
    detail = response.json()["detail"]
    org_ids = {m["organization_id"] for m in detail["memberships"]}
    assert org_ids == {str(org_a.id), str(org_b.id)}

    # Now with organization_id specified, it succeeds.
    response = client.post(
        "/auth/login",
        json={"email": "dave@example.com", "password": "correct-horse-battery", "organization_id": str(org_a.id)},
    )
    assert response.status_code == 200
    assert response.json()["organization_id"] == str(org_a.id)
