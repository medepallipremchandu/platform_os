"""The provider-configuration API: authorization, the write-only secret posture, and the
one-enabled-provider-per-kind invariant."""
import uuid

from app.api.providers import LOGS_READ, PROVIDERS_MANAGE, PROVIDERS_READ

SMTP_BODY = {
    "kind": "email",
    "provider": "smtp",
    "name": "Acme relay",
    "config": {
        "host": "smtp.acme.test",
        "port": 587,
        "from_address": "no-reply@acme.test",
        "username": "acme",
        "password": "hunter2",
    },
    "is_enabled": True,
}


def _create(client, org_id, body=None):
    return client.post(f"/organizations/{org_id}/notification-providers", json=body or SMTP_BODY)


def test_catalog_is_readable_and_marks_secret_fields(client):
    response = client.get("/providers/catalog")
    assert response.status_code == 200
    smtp = next(spec for spec in response.json() if spec["key"] == "smtp")
    assert next(f for f in smtp["fields"] if f["name"] == "password")["secret"] is True


def test_a_secret_is_never_returned_by_any_read_path(client, as_actor, org_id):
    as_actor(org_id=org_id, permissions=[PROVIDERS_MANAGE, PROVIDERS_READ])
    created = _create(client, org_id)
    assert created.status_code == 201
    body = created.json()
    assert "password" not in body["config"]
    assert "hunter2" not in created.text
    # The console still needs to know a password IS set, without seeing it.
    assert body["secrets_set"] == ["password"]

    listed = client.get(f"/organizations/{org_id}/notification-providers")
    assert "hunter2" not in listed.text


def test_updating_without_resending_the_secret_keeps_the_stored_one(client, as_actor, org_id, db):
    from app.core_crypto import decrypt_secrets
    from app.models import NotificationProviderConfig

    as_actor(org_id=org_id, permissions=[PROVIDERS_MANAGE])
    config_id = _create(client, org_id).json()["id"]

    response = client.patch(
        f"/organizations/{org_id}/notification-providers/{config_id}",
        json={"config": {"host": "smtp.acme.test", "port": 2525, "from_address": "no-reply@acme.test", "username": "acme"}},
    )
    assert response.status_code == 200
    assert response.json()["config"]["port"] == 2525

    row = db.get(NotificationProviderConfig, uuid.UUID(config_id))
    db.refresh(row)
    assert decrypt_secrets(row.secrets_encrypted) == {"password": "hunter2"}


def test_enabling_one_provider_disables_the_others_of_the_same_kind(client, as_actor, org_id):
    as_actor(org_id=org_id, permissions=[PROVIDERS_MANAGE, PROVIDERS_READ])
    first = _create(client, org_id).json()
    second = _create(
        client,
        org_id,
        {**SMTP_BODY, "name": "Backup relay", "config": {**SMTP_BODY["config"], "host": "smtp2.acme.test"}},
    ).json()

    rows = {row["id"]: row for row in client.get(f"/organizations/{org_id}/notification-providers").json()}
    assert rows[first["id"]]["is_enabled"] is False
    assert rows[second["id"]]["is_enabled"] is True


def test_an_email_and_a_queue_provider_can_both_be_enabled(client, as_actor, org_id):
    """The one-enabled rule is per KIND, not per organization - the two axes are independent."""
    as_actor(org_id=org_id, permissions=[PROVIDERS_MANAGE, PROVIDERS_READ])
    _create(client, org_id)
    _create(
        client,
        org_id,
        {
            "kind": "queue",
            "provider": "redis",
            "name": "Acme Redis",
            "config": {"host": "redis.acme.test", "port": 6379},
            "is_enabled": True,
        },
    )
    enabled = [row for row in client.get(f"/organizations/{org_id}/notification-providers").json() if row["is_enabled"]]
    assert sorted(row["kind"] for row in enabled) == ["email", "queue"]


def test_an_incomplete_config_is_a_400_not_a_500(client, as_actor, org_id):
    as_actor(org_id=org_id, permissions=[PROVIDERS_MANAGE])
    response = _create(client, org_id, {**SMTP_BODY, "config": {"port": 587}})
    assert response.status_code == 400
    assert "host" in response.json()["detail"].lower()


def test_an_unknown_provider_is_a_400(client, as_actor, org_id):
    as_actor(org_id=org_id, permissions=[PROVIDERS_MANAGE])
    response = _create(client, org_id, {**SMTP_BODY, "provider": "carrier-pigeon"})
    assert response.status_code == 400


def test_a_token_scoped_to_another_organization_cannot_read_or_write_this_ones_providers(client, as_actor, org_id):
    """The security-critical one: holding the permission is not enough - a token issued for org A
    must not reach org B's mail credentials."""
    as_actor(org_id=uuid.uuid4(), permissions=[PROVIDERS_MANAGE, PROVIDERS_READ])
    assert client.get(f"/organizations/{org_id}/notification-providers").status_code == 403
    assert _create(client, org_id).status_code == 403


def test_missing_the_permission_is_a_403_even_inside_the_right_organization(client, as_actor, org_id):
    as_actor(org_id=org_id, permissions=[])
    assert client.get(f"/organizations/{org_id}/notification-providers").status_code == 403


def test_a_superadmin_can_administer_any_organization(client, as_actor, org_id):
    as_actor(org_id=None, permissions=[], is_superadmin=True)
    assert _create(client, org_id).status_code == 201
    assert client.get(f"/organizations/{org_id}/notification-providers").status_code == 200


def test_a_config_belonging_to_another_organization_reads_as_not_found(client, as_actor, org_id):
    as_actor(org_id=None, permissions=[], is_superadmin=True)
    config_id = _create(client, org_id).json()["id"]

    other_org = uuid.uuid4()
    response = client.patch(
        f"/organizations/{other_org}/notification-providers/{config_id}", json={"name": "stolen"}
    )
    assert response.status_code == 404


def test_archiving_also_disables(client, as_actor, org_id):
    as_actor(org_id=org_id, permissions=[PROVIDERS_MANAGE])
    config_id = _create(client, org_id).json()["id"]
    archived = client.delete(f"/organizations/{org_id}/notification-providers/{config_id}").json()
    assert archived["archived_at"] is not None
    assert archived["is_enabled"] is False
    assert client.get(f"/organizations/{org_id}/notification-providers").json() == []


def test_resolved_shows_the_platform_default_until_a_provider_is_enabled(client, as_actor, org_id):
    as_actor(org_id=org_id, permissions=[PROVIDERS_READ, PROVIDERS_MANAGE])
    before = client.get(f"/organizations/{org_id}/notification-providers/resolved").json()
    assert before == {
        "email_provider": "console",
        "email_scope": "platform",
        "queue_provider": "platform-default",
        "queue_scope": "platform",
    }

    _create(client, org_id)
    after = client.get(f"/organizations/{org_id}/notification-providers/resolved").json()
    assert after["email_provider"] == "smtp"
    assert after["email_scope"] == "organization"


def test_test_connection_records_a_failure_without_raising(client, as_actor, org_id):
    as_actor(org_id=org_id, permissions=[PROVIDERS_MANAGE, PROVIDERS_READ])
    config_id = _create(
        client,
        org_id,
        {**SMTP_BODY, "config": {**SMTP_BODY["config"], "host": "smtp.invalid.test", "timeout_seconds": 1}},
    ).json()["id"]

    response = client.post(f"/organizations/{org_id}/notification-providers/{config_id}/test")
    assert response.status_code == 200
    assert response.json()["ok"] is False

    row = next(r for r in client.get(f"/organizations/{org_id}/notification-providers").json() if r["id"] == config_id)
    assert row["last_test_ok"] is False
    assert row["last_test_at"] is not None


def test_email_logs_are_scoped_to_the_organization(client, as_actor, org_id, db):
    from app.models import EmailLog

    db.add(EmailLog(organization_id=org_id, to_email="a@example.com", template="user_invite", status="sent"))
    db.add(EmailLog(organization_id=uuid.uuid4(), to_email="b@example.com", template="user_invite", status="sent"))
    db.commit()

    as_actor(org_id=org_id, permissions=[LOGS_READ])
    page = client.get(f"/organizations/{org_id}/email-logs").json()
    assert page["total"] == 1
    assert page["items"][0]["to_email"] == "a@example.com"


def test_replacing_an_enabled_provider_does_not_collide_with_the_partial_unique_index(client, as_actor, org_id, db):
    """Regression: the swap has to disable the incumbent BEFORE inserting its replacement.

    `uq_notification_provider_enabled_per_kind` is a partial unique index, and Postgres checks an
    index per-statement - it cannot be deferred the way a constraint can. Inserting the new
    enabled row first therefore collides with the very row the same call is about to disable.
    This escaped once because the test schema was built by create_all() while the index existed
    only in the migration; it is now declared on the model too, so this test has real teeth."""
    from app.models import NotificationProviderConfig

    as_actor(org_id=org_id, permissions=[PROVIDERS_MANAGE, PROVIDERS_READ])
    for index in range(3):
        response = _create(
            client,
            org_id,
            {**SMTP_BODY, "name": f"Relay {index}", "config": {**SMTP_BODY["config"], "host": f"smtp{index}.acme.test"}},
        )
        assert response.status_code == 201, response.text

    enabled = (
        db.query(NotificationProviderConfig)
        .filter(NotificationProviderConfig.organization_id == org_id, NotificationProviderConfig.is_enabled.is_(True))
        .all()
    )
    assert len(enabled) == 1
    assert enabled[0].name == "Relay 2"
