"""The two Celery tasks that make up the notification pipeline.

    notifications.send_email      dispatcher - runs on the PLATFORM broker, decides WHICH broker
                                  this organization's delivery is enqueued onto
    notifications.deliver_email   delivery   - renders, hands the message to the organization's
                                  email provider, writes the EmailLog row

Cross-service contract with iam-service (the only producer today), fixed:

    task     "notifications.send_email"
    kwargs   {to_email: str, template: str, context: dict, organization_id: str | None}
    template one of app.templates.TEMPLATE_NAMES

`organization_id` is the only field added on top of the original contract, and it is optional -
a producer that omits it gets the platform default provider, i.e. exactly the behaviour that
existed before tenant providers.

Dispatch always enqueues rather than ever delivering inline, even when the organization has no
queue of its own (in which case delivery is enqueued back onto the platform broker and the same
worker picks it up). Uniformity is worth the extra hop: retry, backoff and acknowledgement
behave identically whether or not a tenant broker is in play, instead of the common path
quietly having different failure semantics from the tenant path.
"""
import logging
import uuid
from datetime import datetime, timezone

from celery import shared_task

from app.celery_app import celery_app, tenant_celery_app
from app.config import get_settings
from app.database import get_db_session
from app.models import EmailLog
from app.providers.base import ProviderConfigError, ProviderSendError
from app.services import resolver
from app.templates import render_email

logger = logging.getLogger("app.tasks")

SEND_EMAIL_TASK = "notifications.send_email"
DELIVER_EMAIL_TASK = "notifications.deliver_email"

_settings = get_settings()


def _as_uuid(value) -> uuid.UUID | None:
    if not value:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        logger.warning("Ignoring malformed organization_id %r on a notification task", value)
        return None


def _record(db, *, organization_id, to_email, template, status, provider, scope, error=None, sent=False) -> EmailLog:
    row = EmailLog(
        organization_id=organization_id,
        to_email=to_email,
        template=template,
        status=status,
        provider=provider,
        provider_scope=scope,
        error_message=error,
        sent_at=datetime.now(timezone.utc) if sent else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@celery_app.task(name=SEND_EMAIL_TASK, max_retries=0)
def send_email(*, to_email: str, template: str, context: dict, organization_id: str | None = None):
    """Tier-1 dispatcher, consumed from the platform broker.

    max_retries=0 is deliberate: the only fallible thing here is the re-publish to a tenant
    broker, and the right response to that is to fall back to the platform broker immediately,
    not to retry a broker that is down. All retry/backoff lives on `deliver_email`, where the
    actual network send happens."""
    organization_uuid = _as_uuid(organization_id)
    kwargs = {"to_email": to_email, "template": template, "context": context, "organization_id": organization_id}

    db = get_db_session()
    try:
        queue = resolver.resolve_queue_provider(db, organization_uuid)
        if queue is not None:
            try:
                app = tenant_celery_app(queue.provider.broker_url(), queue.provider.transport_options())
                app.send_task(DELIVER_EMAIL_TASK, kwargs=kwargs)
            except Exception as exc:
                # The tenant's broker is unreachable or misconfigured. Falling back to the
                # platform broker is strictly better than dropping an invite on the floor; the
                # EmailLog row records that the tenant queue was bypassed, so it is visible
                # rather than silently absorbed.
                logger.exception(
                    "Publish to organization %s's own queue failed - falling back to the platform broker",
                    organization_uuid,
                )
                _record(
                    db,
                    organization_id=organization_uuid,
                    to_email=to_email,
                    template=template,
                    status="failed",
                    provider=queue.key,
                    scope=resolver.SCOPE_ORGANIZATION,
                    error=f"Publish to the organization's own queue failed, used the platform broker instead: {exc}",
                )
            else:
                _record(
                    db,
                    organization_id=organization_uuid,
                    to_email=to_email,
                    template=template,
                    status="queued_to_org_queue",
                    provider=queue.key,
                    scope=resolver.SCOPE_ORGANIZATION,
                )
                logger.info(
                    "Handed %s for %s to organization %s's own %s queue",
                    template,
                    to_email,
                    organization_uuid,
                    queue.key,
                )
                return {"status": "queued_to_org_queue", "provider": queue.key}
    finally:
        db.close()

    # Looked up on `celery_app` explicitly rather than calling the module-level
    # `deliver_email.apply_async` proxy: @shared_task resolves against whatever the process's
    # current app happens to be, and this must always be the platform one. Going through the
    # bound Task (rather than celery_app.send_task) is also what lets task_always_eager work in
    # tests - send_task bypasses eager mode entirely.
    celery_app.tasks[DELIVER_EMAIL_TASK].apply_async(kwargs=kwargs)
    return {"status": "queued", "provider": "platform"}


@shared_task(name=DELIVER_EMAIL_TASK, bind=True, max_retries=_settings.NOTIFICATIONS_MAX_RETRIES)
def deliver_email(self, *, to_email: str, template: str, context: dict, organization_id: str | None = None):
    """Tier-2 delivery: render, resolve the organization's email provider, send, log.

    Declared with @shared_task rather than bound to one Celery app because the very same
    function is consumed from two different brokers - the platform one, and (for an organization
    with its own queue provider) theirs. See run_worker.py.

    Retries cover ProviderSendError only, i.e. genuinely transient remote failures. A bad
    template name or a missing context key is a bug in the producer: retrying it three times
    just delays the identical failure, so it is recorded as failed once and dropped. Exactly one
    EmailLog row is written per email, on the terminal outcome - never one per attempt."""
    organization_uuid = _as_uuid(organization_id)
    settings = get_settings()
    db = get_db_session()
    try:
        try:
            rendered = render_email(template, context)
        except (ValueError, KeyError) as exc:
            logger.error("Non-retryable render failure for template %r to %s: %s", template, to_email, exc)
            _record(
                db,
                organization_id=organization_uuid,
                to_email=to_email,
                template=template,
                status="failed",
                provider=None,
                scope=None,
                error=f"Could not render template: {exc}",
            )
            return {"status": "failed", "error": str(exc)}

        resolved = resolver.resolve_email_provider(db, organization_uuid)

        try:
            status = resolved.provider.send(to_email=to_email, rendered=rendered)
        except ProviderConfigError as exc:
            logger.error(
                "Email provider %s is misconfigured for organization %s: %s", resolved.key, organization_uuid, exc
            )
            _record(
                db,
                organization_id=organization_uuid,
                to_email=to_email,
                template=template,
                status="failed",
                provider=resolved.key,
                scope=resolved.scope,
                error=str(exc),
            )
            return {"status": "failed", "error": str(exc)}
        except ProviderSendError as exc:
            attempt = self.request.retries or 0
            if attempt < self.max_retries:
                countdown = settings.NOTIFICATIONS_RETRY_BACKOFF_SECONDS * (2**attempt)
                logger.warning(
                    "Email delivery to %s failed (attempt %s/%s), retrying in %ss: %s",
                    to_email,
                    attempt + 1,
                    self.max_retries + 1,
                    countdown,
                    exc,
                )
                raise self.retry(exc=exc, countdown=countdown)
            logger.error("Email delivery to %s failed after %s attempts: %s", to_email, attempt + 1, exc)
            _record(
                db,
                organization_id=organization_uuid,
                to_email=to_email,
                template=template,
                status="failed",
                provider=resolved.key,
                scope=resolved.scope,
                error=str(exc),
            )
            return {"status": "failed", "error": str(exc)}

        _record(
            db,
            organization_id=organization_uuid,
            to_email=to_email,
            template=template,
            status=status,
            provider=resolved.key,
            scope=resolved.scope,
            sent=(status == "sent"),
        )
        return {"status": status, "provider": resolved.key, "scope": resolved.scope}
    finally:
        db.close()
