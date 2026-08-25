from tests.helpers import add_membership, create_org, create_user


def _login(client, email="erin@example.com", password="correct-horse-battery"):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_refresh_rotates_token(client, db):
    org = create_org(db)
    user = create_user(db, "erin@example.com", "correct-horse-battery")
    add_membership(db, user, org)

    login_resp = _login(client)
    refresh_token = login_resp.json()["refresh_token"]

    resp = client.post("/auth/token/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["refresh_token"] != refresh_token


def test_refresh_reuse_detection_revokes_family(client, db):
    org = create_org(db)
    user = create_user(db, "frank@example.com", "correct-horse-battery")
    add_membership(db, user, org)

    login_resp = _login(client, email="frank@example.com")
    original_refresh = login_resp.json()["refresh_token"]

    first_rotation = client.post("/auth/token/refresh", json={"refresh_token": original_refresh})
    assert first_rotation.status_code == 200
    rotated_refresh = first_rotation.json()["refresh_token"]

    # Reusing the already-rotated (now-revoked) original token is theft/replay evidence.
    reuse_attempt = client.post("/auth/token/refresh", json={"refresh_token": original_refresh})
    assert reuse_attempt.status_code == 401

    # The whole family, including the token minted by the first (legitimate) rotation, is
    # now revoked too.
    followup = client.post("/auth/token/refresh", json={"refresh_token": rotated_refresh})
    assert followup.status_code == 401


def test_refresh_invalid_token_rejected(client):
    resp = client.post("/auth/token/refresh", json={"refresh_token": "not-a-real-token"})
    assert resp.status_code == 401
