"""Resolving WHICH provider handles a given organization's notification.

One rule, applied to both axes: an organization's own enabled provider wins; otherwise the
platform default applies. That fallback is what makes this whole feature additive - an
organization that has configured nothing behaves exactly as it did before tenant providers
existed, and no migration or backfill is needed to keep it working.
"""
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import NotificationProviderConfig
from app.providers.base import Provider
from app.providers.email import ConsoleEmailProvider, EmailProvider, SmtpEmailProvider
from app.providers.queue import QueueProvider
from app.providers.registry import instantiate

logger = logging.getLogger("app.resolver")

SCOPE_ORGANIZATION = "organization"
SCOPE_PLATFORM = "platform"


@dataclass(frozen=True)
class ResolvedProvider:
    provider: Provider
    key: str
    scope: str
    config_id: uuid.UUID | None


def active_config(db: Session, organization_id: uuid.UUID | None, kind: str) -> NotificationProviderConfig | None:
    """The organization's one enabled, non-archived config of this kind, if any. `organization_id`
    is None for a notification that belongs to no organization (a password reset for an address
    the producer could not attribute), which resolves straight to the platform default."""
    if organization_id is None:
        return None
    return db.execute(
        select(NotificationProviderConfig).where(
            NotificationProviderConfig.organization_id == organization_id,
            NotificationProviderConfig.kind == kind,
            NotificationProviderConfig.is_enabled.is_(True),
            NotificationProviderConfig.archived_at.is_(None),
        )
    ).scalars().first()


def platform_email_provider(settings: Settings | None = None) -> EmailProvider:
    """The platform default: real SMTP if .env carries a host, otherwise the console sink.

    The console fallback is the deliberate sandbox posture, not an oversight - it logs the fully
    rendered email including the set-password link, so the invite and forgot-password flows are
    exercisable end to end with no SMTP credentials anywhere."""
    settings = settings or get_settings()
    if not settings.SMTP_HOST.strip():
        return ConsoleEmailProvider({"from_address": settings.SMTP_FROM_ADDRESS})
    return SmtpEmailProvider(
        {
            "host": settings.SMTP_HOST,
            "port": settings.SMTP_PORT,
            "username": settings.SMTP_USERNAME,
            "password": settings.SMTP_PASSWORD,
            "from_address": settings.SMTP_FROM_ADDRESS,
            "use_tls": settings.SMTP_USE_TLS,
            "verify_cert": settings.SMTP_VERIFY_CERT,
        }
    )


def resolve_email_provider(db: Session, organization_id: uuid.UUID | None) -> ResolvedProvider:
    row = active_config(db, organization_id, "email")
    if row is not None:
        try:
            provider = instantiate("email", row.provider, row.config, row.secrets_encrypted)
            return ResolvedProvider(provider, row.provider, SCOPE_ORGANIZATION, row.id)
        except Exception:
            # A tenant's broken or undecryptable config must degrade to the platform default,
            # never strand the email. Logged loudly (with the config id, not its contents) so
            # the failure is visible instead of silently absorbed.
            logger.exception(
                "Organization %s has an enabled email provider (config %s) that failed to load - "
                "falling back to the platform default",
                organization_id,
                row.id,
            )
    return ResolvedProvider(platform_email_provider(), "smtp" if get_settings().SMTP_HOST.strip() else "console", SCOPE_PLATFORM, None)


def resolve_queue_provider(db: Session, organization_id: uuid.UUID | None) -> ResolvedProvider | None:
    """None means "no tenant queue" - deliver inline on the platform worker. There is no
    platform-default *tenant* queue: the platform broker is tier-1 ingest, which the dispatcher
    is already running on, so falling back to it means simply not making a second hop."""
    row = active_config(db, organization_id, "queue")
    if row is None:
        return None
    try:
        provider = instantiate("queue", row.provider, row.config, row.secrets_encrypted)
    except Exception:
        logger.exception(
            "Organization %s has an enabled queue provider (config %s) that failed to load - "
            "delivering inline on the platform worker instead",
            organization_id,
            row.id,
        )
        return None
    assert isinstance(provider, QueueProvider)
    return ResolvedProvider(provider, row.provider, SCOPE_ORGANIZATION, row.id)
