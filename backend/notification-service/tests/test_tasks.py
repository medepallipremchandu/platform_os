"""The delivery pipeline end to end, with Celery eager so both hops run for real in-process."""
import uuid

from sqlalchemy import select

from app.models import EmailLog
from app.providers.base import ProviderSendError
from app.providers.email import SmtpEmailProvider
from app.services import provider_config_service
from app.tasks import deliver_email, send_email

INVITE_CONTEXT = {
    "organization_name": "Acme",
    "display_name": "Dana",
    "set_password_url": "http://localhost:5175/set-password?token=abc123",
}


def _logs(db, to_email: str) -> list[EmailLog]:
    return list(db.execute(select(EmailLog).where(EmailLog.to_email == to_email)).scalars().all())


def test_with_no_provider_configured_the_email_is_logged_not_sent(db, org_id, caplog):
    caplog.set_level("INFO")
    deliver_email.apply(
        kwargs={
            "to_email": "dana@example.com",
            "template": "org_admin_invite",
            "context": INVITE_CONTEXT,
            "organization_id": str(org_id),
        }
    )
    rows = _logs(db, "dana@example.com")
    assert len(rows) == 1
    assert rows[0].status == "logged_no_smtp_configured"
    assert rows[0].provider == "console"
    assert rows[0].provider_scope == "platform"
    assert rows[0].sent_at is None
    # The whole point of the console sink: the set-password link is recoverable from the log,
    # so the invite flow is exercisable with no SMTP anywhere.
    assert "set-password?token=abc123" in caplog.text


def test_all_three_templates_render_and_log(db, org_id):
    cases = [
        ("org_admin_invite", INVITE_CONTEXT),
        ("user_invite", INVITE_CONTEXT),
        ("password_reset", {"display_name": "Dana", "reset_url": "http://localhost:5175/set-password?token=r"}),
    ]
    for template, context in cases:
        deliver_email.apply(
            kwargs={
                "to_email": f"{template}@example.com",
                "template": template,
                "context": context,
                "organization_id": str(org_id),
            }
        )
        rows = _logs(db, f"{template}@example.com")
        assert len(rows) == 1, template
        assert rows[0].status == "logged_no_smtp_configured", template


def test_an_unknown_template_fails_once_and_is_not_retried(db, org_id):
    deliver_email.apply(
        kwargs={
            "to_email": "dana@example.com",
            "template": "carrier_pigeon",
            "context": {},
            "organization_id": str(org_id),
        }
    )
    rows = _logs(db, "dana@example.com")
    assert len(rows) == 1
    assert rows[0].status == "failed"
    assert "carrier_pigeon" in rows[0].error_message


def test_an_organizations_own_email_provider_takes_precedence_over_the_platform_default(db, org_id, monkeypatch):
    sent: list[tuple] = []
    monkeypatch.setattr(
        SmtpEmailProvider, "send", lambda self, *, to_email, rendered: sent.append((to_email, rendered.subject)) or "sent"
    )
    provider_config_service.create_config(
        db,
        org_id,
        kind="email",
        provider="smtp",
        name="Acme relay",
        config={"host": "smtp.acme.test", "port": 587, "from_address": "no-reply@acme.test", "password": "hunter2"},
        is_enabled=True,
    )

    deliver_email.apply(
        kwargs={
            "to_email": "dana@example.com",
            "template": "user_invite",
            "context": INVITE_CONTEXT,
            "organization_id": str(org_id),
        }
    )

    assert len(sent) == 1
    rows = _logs(db, "dana@example.com")
    assert rows[0].status == "sent"
    assert rows[0].provider == "smtp"
    assert rows[0].provider_scope == "organization"
    assert rows[0].sent_at is not None


def test_another_organizations_provider_is_never_used(db, org_id, monkeypatch):
    """The fallback is per-organization: configuring org A must not change org B's behaviour."""
    monkeypatch.setattr(SmtpEmailProvider, "send", lambda self, *, to_email, rendered: "sent")
    provider_config_service.create_config(
        db,
        org_id,
        kind="email",
        provider="smtp",
        name="Acme relay",
        config={"host": "smtp.acme.test", "port": 587, "from_address": "no-reply@acme.test"},
        is_enabled=True,
    )

    other_org = uuid.uuid4()
    deliver_email.apply(
        kwargs={
            "to_email": "someone-else@example.com",
            "template": "user_invite",
            "context": INVITE_CONTEXT,
            "organization_id": str(other_org),
        }
    )
    rows = _logs(db, "someone-else@example.com")
    assert rows[0].provider == "console"
    assert rows[0].provider_scope == "platform"


def test_a_disabled_provider_is_ignored(db, org_id):
    provider_config_service.create_config(
        db,
        org_id,
        kind="email",
        provider="smtp",
        name="Draft relay",
        config={"host": "smtp.acme.test", "port": 587, "from_address": "no-reply@acme.test"},
        is_enabled=False,
    )
    deliver_email.apply(
        kwargs={
            "to_email": "dana@example.com",
            "template": "user_invite",
            "context": INVITE_CONTEXT,
            "organization_id": str(org_id),
        }
    )
    assert _logs(db, "dana@example.com")[0].provider == "console"


def test_a_transient_send_failure_retries_and_then_records_one_failed_row(db, org_id, monkeypatch):
    attempts = {"n": 0}

    def _always_fail(self, *, to_email, rendered):
        attempts["n"] += 1
        raise ProviderSendError("connection refused")

    monkeypatch.setattr(SmtpEmailProvider, "send", _always_fail)
    provider_config_service.create_config(
        db,
        org_id,
        kind="email",
        provider="smtp",
        name="Acme relay",
        config={"host": "smtp.acme.test", "port": 587, "from_address": "no-reply@acme.test"},
        is_enabled=True,
    )

    deliver_email.apply(
        kwargs={
            "to_email": "dana@example.com",
            "template": "user_invite",
            "context": INVITE_CONTEXT,
            "organization_id": str(org_id),
        },
        throw=False,
    )

    # CELERY_MAX_RETRIES=2 in the test env -> one initial attempt plus two retries.
    assert attempts["n"] == 3
    rows = _logs(db, "dana@example.com")
    assert len(rows) == 1, "exactly one EmailLog row per email, on the terminal outcome"
    assert rows[0].status == "failed"
    assert "connection refused" in rows[0].error_message


def test_dispatch_hands_off_to_an_organizations_own_queue(db, org_id, monkeypatch):
    published: list[dict] = []

    class _FakeApp:
        def send_task(self, name, kwargs=None):
            published.append({"name": name, "kwargs": kwargs})

    monkeypatch.setattr("app.tasks.tenant_celery_app", lambda url, options=None: _FakeApp())
    provider_config_service.create_config(
        db,
        org_id,
        kind="queue",
        provider="redis",
        name="Acme Redis",
        config={"host": "redis.acme.test", "port": 6379, "db": 0, "password": "s3cret"},
        is_enabled=True,
    )

    send_email.apply(
        kwargs={
            "to_email": "dana@example.com",
            "template": "user_invite",
            "context": INVITE_CONTEXT,
            "organization_id": str(org_id),
        }
    )

    assert published == [
        {
            "name": "notifications.deliver_email",
            "kwargs": {
                "to_email": "dana@example.com",
                "template": "user_invite",
                "context": INVITE_CONTEXT,
                "organization_id": str(org_id),
            },
        }
    ]
    rows = _logs(db, "dana@example.com")
    assert [row.status for row in rows] == ["queued_to_org_queue"]
    assert rows[0].provider == "redis"


def test_a_broken_tenant_queue_falls_back_to_the_platform_broker_instead_of_dropping_the_email(
    db, org_id, monkeypatch
):
    def _explode(url, options=None):
        raise OSError("redis.acme.test: name or service not known")

    monkeypatch.setattr("app.tasks.tenant_celery_app", _explode)
    provider_config_service.create_config(
        db,
        org_id,
        kind="queue",
        provider="redis",
        name="Acme Redis",
        config={"host": "redis.acme.test", "port": 6379},
        is_enabled=True,
    )

    send_email.apply(
        kwargs={
            "to_email": "dana@example.com",
            "template": "user_invite",
            "context": INVITE_CONTEXT,
            "organization_id": str(org_id),
        }
    )

    statuses = [row.status for row in _logs(db, "dana@example.com")]
    # One row recording that the tenant queue was bypassed, and one for the email that still
    # got delivered via the platform path.
    assert "failed" in statuses
    assert "logged_no_smtp_configured" in statuses


def test_dispatch_without_a_tenant_queue_goes_straight_down_the_platform_path(db, org_id):
    send_email.apply(
        kwargs={
            "to_email": "dana@example.com",
            "template": "user_invite",
            "context": INVITE_CONTEXT,
            "organization_id": str(org_id),
        }
    )
    rows = _logs(db, "dana@example.com")
    assert [row.status for row in rows] == ["logged_no_smtp_configured"]


def test_a_notification_with_no_organization_uses_the_platform_default(db):
    deliver_email.apply(
        kwargs={
            "to_email": "nobody@example.com",
            "template": "password_reset",
            "context": {"display_name": "Nobody", "reset_url": "http://localhost:5175/set-password?token=x"},
            "organization_id": None,
        }
    )
    rows = _logs(db, "nobody@example.com")
    assert rows[0].organization_id is None
    assert rows[0].provider_scope == "platform"
