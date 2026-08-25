"""iam-service's side of the notification contract: publish, never consume.

The two services share a broker URL and a task name - nothing else. No shared code, no shared
models, no import of notification-service from here. That is what lets the notification worker
be restarted, redeployed or temporarily absent without iam-service noticing.

Contract (see notification-service/app/tasks.py, which owns the consumer):

    task     "notifications.send_email"
    kwargs   {to_email, template, context, organization_id}
    template "org_admin_invite" | "user_invite" | "password_reset"
    context  org_admin_invite / user_invite: {organization_name, display_name, set_password_url}
             password_reset:                 {display_name, reset_url}

`organization_id` is what lets notification-service pick THAT organization's own email and
queue providers instead of the platform defaults. Omitting it is legal and means "use the
platform default".

**A queue-publish failure must never break the business operation it accompanies.** An invite
that creates the user but fails to send the email is recoverable - the operator resends it. An
invite that 500s after the user row was written is not. So every publish here is wrapped:
logged loudly, then swallowed. The link is also logged locally at INFO as a last resort, so a
developer with no worker running can still complete the flow.
"""
import logging
import os
import uuid
from functools import lru_cache
from urllib.parse import quote

from app.config import Settings, get_settings

logger = logging.getLogger("app.notifications")

SEND_EMAIL_TASK = "notifications.send_email"

TEMPLATE_ORG_ADMIN_INVITE = "org_admin_invite"
TEMPLATE_USER_INVITE = "user_invite"
TEMPLATE_PASSWORD_RESET = "password_reset"


@lru_cache
def _producer():
    """A publish-only Celery app. Built lazily and cached so importing this module (and
    therefore the whole service) never depends on the broker being reachable - a down broker
    should degrade email, not prevent iam-service from starting."""
    # celery.app.utils.Settings.broker_url is a PROPERTY returning os.environ["CELERY_BROKER_URL"]
    # ahead of anything configured here - a hard override, re-read on every access. This service
    # does not use that convention (its setting is NOTIFICATIONS_BROKER_URL), so the variable can
    # only do harm: stripped loudly before the producer is built.
    for hijacking_var in ("CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"):
        if os.environ.pop(hijacking_var, None) is not None:
            logger.warning(
                "%s was set in the environment and has been ignored - configure "
                "NOTIFICATIONS_BROKER_URL instead.",
                hijacking_var,
            )

    from celery import Celery

    settings = get_settings()
    app = Celery("talentos-iam-producer", set_as_current=False)
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_backend=None,
        task_default_queue=settings.NOTIFICATIONS_QUEUE_NAME,
        broker_connection_retry_on_startup=True,
    )
    app.conf.broker_url = settings.NOTIFICATIONS_BROKER_URL
    return app


def set_password_url(settings: Settings, token: str) -> str:
    """Where an invited or password-resetting user lands to choose a password.

    One URL for both flows on purpose: invites and forgot-password share the same token type
    and the same confirm endpoint, so they share the same landing page (see
    password_reset_service, and portal's SetPasswordPage)."""
    return f"{settings.PORTAL_URL.rstrip('/')}/set-password?token={quote(token, safe='')}"


def send_email(
    settings: Settings,
    *,
    to_email: str,
    template: str,
    context: dict,
    organization_id: uuid.UUID | None = None,
) -> bool:
    """Publish one email task. Returns whether the publish succeeded; callers ignore it, because
    by contract nothing here is allowed to fail the surrounding operation."""
    if not settings.NOTIFICATIONS_ENABLED:
        logger.info("Notifications disabled - would have sent %r to %s: %s", template, to_email, context)
        return False
    try:
        _producer().send_task(
            SEND_EMAIL_TASK,
            kwargs={
                "to_email": to_email,
                "template": template,
                "context": context,
                "organization_id": str(organization_id) if organization_id else None,
            },
        )
        logger.info("Queued %r email to %s (organization=%s)", template, to_email, organization_id)
        return True
    except Exception:
        logger.exception(
            "Could not queue %r email to %s - continuing anyway. Context: %s", template, to_email, context
        )
        return False


def send_invite(
    settings: Settings,
    *,
    to_email: str,
    display_name: str | None,
    organization_name: str,
    organization_id: uuid.UUID,
    token: str,
    is_org_admin: bool = False,
) -> bool:
    url = set_password_url(settings, token)
    # Logged locally as well as queued: with no worker running (or no SMTP anywhere), this line
    # is what lets a developer actually complete the invite flow.
    logger.info("Set-password link for %s: %s", to_email, url)
    return send_email(
        settings,
        to_email=to_email,
        template=TEMPLATE_ORG_ADMIN_INVITE if is_org_admin else TEMPLATE_USER_INVITE,
        context={
            "organization_name": organization_name,
            "display_name": display_name or to_email,
            "set_password_url": url,
        },
        organization_id=organization_id,
    )


def send_password_reset(
    settings: Settings,
    *,
    to_email: str,
    display_name: str | None,
    token: str,
    organization_id: uuid.UUID | None = None,
) -> bool:
    url = set_password_url(settings, token)
    logger.info("Password reset link for %s: %s", to_email, url)
    return send_email(
        settings,
        to_email=to_email,
        template=TEMPLATE_PASSWORD_RESET,
        context={"display_name": display_name or to_email, "reset_url": url},
        organization_id=organization_id,
    )
