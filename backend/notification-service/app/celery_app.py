"""Celery wiring for both tiers of the notification pipeline.

Tier 1 - ingest (`celery_app`): the platform broker, fixed in .env. Every producer publishes
`notifications.send_email` here. It is deliberately not tenant-configurable, because a tenant
misconfiguring their own broker must never be able to break organization creation or a
password reset - producers stay decoupled from tenant state entirely.

Tier 2 - delivery (`tenant_celery_app`): an organization that has enabled its own queue provider
gets `notifications.deliver_email` re-published onto THEIR broker instead of being delivered
inline. That app is producer-only from the dispatcher's point of view; the consumer for it is
`run_worker.py --organization <id>`, the same code pointed at the tenant broker.

Windows note: Celery's default prefork pool does not work on Windows. Both entry points are
documented to run with `--pool=solo`; see README.md.
"""
import logging
import os

from celery import Celery

from app.config import get_settings

logger = logging.getLogger("app.celery")

# --- Guard: Celery's own environment-variable convention must not be in play here ------------
#
# celery.app.utils.Settings.broker_url is a PROPERTY that returns os.environ["CELERY_BROKER_URL"]
# ahead of anything the application configures - not a default, a hard override, re-read on every
# access. CELERY_RESULT_BACKEND behaves the same way. In a service that builds one Celery app per
# tenant broker that is catastrophic and silent: every tenant app resolves to whatever that
# variable says, mail is still delivered, nothing errors, and the tenant's queue is simply never
# used.
#
# This service configures brokers explicitly (NOTIFICATIONS_BROKER_URL, plus a per-tenant URL
# from app/providers/queue/) and reads neither variable itself, so a value present in the
# environment can only do harm. It is stripped, loudly. Called from build_celery_app rather than
# only at import, so a variable set later in the process cannot reintroduce the problem.
_HIJACKING_ENV_VARS = ("CELERY_BROKER_URL", "CELERY_RESULT_BACKEND")


def _strip_hijacking_env_vars() -> None:
    for name in _HIJACKING_ENV_VARS:
        if os.environ.pop(name, None) is not None:
            logger.warning(
                "%s was set in the environment and has been ignored. Celery reads it ahead of all "
                "application configuration, which would silently point every per-tenant broker at "
                "it. Configure NOTIFICATIONS_BROKER_URL instead.",
                name,
            )


_strip_hijacking_env_vars()

settings = get_settings()


def _base_config(app: Celery) -> Celery:
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        # No result backend. Nothing ever waits on a send: the caller is a web request that has
        # already returned, and the durable record of what happened is the EmailLog table, not a
        # Celery result row. Leaving it unset also keeps the broker database free of result
        # rows nobody reads.
        result_backend=None,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        broker_connection_retry_on_startup=True,
        # Celery replaces the root logger's handlers by default, which would throw away the
        # rotating file handler configure_logging() installs. That matters more here than in a
        # typical worker: with no email provider configured, the log line IS the delivery
        # record, carrying the set-password link somebody has to be able to find.
        worker_hijack_root_logger=False,
    )
    return app


def build_celery_app(
    name: str, broker_url: str, transport_options: dict | None = None, *, set_as_current: bool = True
) -> Celery:
    # set_as_current=False for the producer-only tenant apps below: creating a Celery instance
    # normally makes it the process-wide "current app", which is what @shared_task resolves
    # against. A dispatcher that publishes to three tenants in a row must not leave the last
    # tenant's broker as the default the rest of the process sees.
    _strip_hijacking_env_vars()
    app = Celery(name, include=["app.tasks"], set_as_current=set_as_current)
    _base_config(app)

    # Assigned explicitly rather than passed as Celery(broker=...). The constructor argument is
    # only "auto-set": Celery lets any real configuration override it - INCLUDING the
    # NOTIFICATIONS_BROKER_URL environment variable, which this service necessarily has in its
    # environment because that is the name of its own platform-broker setting in .env.
    #
    # Left as a constructor argument, every tenant app silently came up pointed at the PLATFORM
    # broker while still reporting itself as the tenant's. Delivery still happened, the UI still
    # said "your Redis", and nothing errored - the tenant queue was simply never used. Setting
    # conf.broker_url after construction is the unambiguous form and beats the environment.
    app.conf.broker_url = broker_url
    if transport_options:
        app.conf.broker_transport_options = transport_options
    return app


celery_app = build_celery_app("talentos-notifications", settings.NOTIFICATIONS_BROKER_URL)
celery_app.conf.task_default_queue = settings.NOTIFICATIONS_QUEUE_NAME

# Producer-only Celery apps for tenant brokers, keyed by (broker_url, frozen transport options).
# Cached because building one opens a connection pool: an organization sending a burst of
# invites should reuse a single producer, and a config change produces a different key so the
# stale entry simply stops being looked up.
_tenant_apps: dict[tuple, Celery] = {}


def tenant_celery_app(broker_url: str, transport_options: dict | None = None) -> Celery:
    key = (broker_url, tuple(sorted((transport_options or {}).items())))
    app = _tenant_apps.get(key)
    if app is None:
        app = build_celery_app("talentos-notifications-tenant", broker_url, transport_options, set_as_current=False)
        app.conf.task_default_queue = settings.NOTIFICATIONS_QUEUE_NAME
        _tenant_apps[key] = app
    return app
