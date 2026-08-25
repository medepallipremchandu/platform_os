"""CRUD for an organization's notification providers.

Two invariants this module owns:

  1. **Secrets are write-only.** A submitted config is split by the provider's own field
     declaration; the secret half is Fernet-encrypted into `secrets_encrypted` and never read
     back out by the API. An update that omits a secret field keeps the stored one, so an
     operator can change an SMTP port without re-typing the password.
  2. **At most one enabled config per (organization, kind).** Enabling one disables the others
     in the same breath, inside the same transaction, so there is never a window where two
     email providers or two brokers both look active.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core_crypto import decrypt_secrets, encrypt_secrets
from app.models import NotificationProviderConfig
from app.providers.base import ProviderConfigError, ProviderSendError
from app.providers.registry import instantiate, provider_class, split_secrets


class NotFoundError(Exception):
    pass


def list_configs(
    db: Session, organization_id: uuid.UUID, *, kind: str | None = None, include_archived: bool = False
) -> list[NotificationProviderConfig]:
    stmt = select(NotificationProviderConfig).where(NotificationProviderConfig.organization_id == organization_id)
    if kind:
        stmt = stmt.where(NotificationProviderConfig.kind == kind)
    if not include_archived:
        stmt = stmt.where(NotificationProviderConfig.archived_at.is_(None))
    stmt = stmt.order_by(NotificationProviderConfig.kind, NotificationProviderConfig.created_at)
    return list(db.execute(stmt).scalars().all())


def get_config(db: Session, organization_id: uuid.UUID, config_id: uuid.UUID) -> NotificationProviderConfig:
    row = db.get(NotificationProviderConfig, config_id)
    # The organization check is part of the lookup, not a separate authorization step: a config
    # belonging to another tenant must be indistinguishable from one that does not exist.
    if row is None or row.organization_id != organization_id:
        raise NotFoundError("Provider configuration not found")
    return row


def _disable_siblings(db: Session, organization_id: uuid.UUID, kind: str, keep_id: uuid.UUID | None) -> None:
    """Clear any other enabled config of this kind, and FLUSH before returning.

    The flush is load-bearing, not tidiness. `uq_notification_provider_enabled_per_kind` is a
    partial unique index, and Postgres checks an index per-statement - a partial unique index
    cannot be deferred the way a constraint can. So the sibling's UPDATE has to reach the
    database before the row that replaces it does, or the insert collides with a row this very
    call is about to disable. Every caller therefore disables BEFORE enabling."""
    stmt = select(NotificationProviderConfig).where(
        NotificationProviderConfig.organization_id == organization_id,
        NotificationProviderConfig.kind == kind,
        NotificationProviderConfig.is_enabled.is_(True),
    )
    changed = False
    for sibling in db.execute(stmt).scalars().all():
        if keep_id is not None and sibling.id == keep_id:
            continue
        sibling.is_enabled = False
        sibling.updated_at = datetime.now(timezone.utc)
        changed = True
    if changed:
        db.flush()


def create_config(
    db: Session,
    organization_id: uuid.UUID,
    *,
    kind: str,
    provider: str,
    name: str,
    config: dict,
    is_enabled: bool = False,
) -> NotificationProviderConfig:
    plain, secrets = split_secrets(kind, provider, config)
    # Construct the provider once before persisting anything: that runs the class's own field
    # validation, so an incomplete config is a 400 at create time rather than a mystery at 3am
    # when the first invite goes out.
    provider_class(kind, provider)({**plain, **secrets})

    # Disable first, insert second - see _disable_siblings for why the order matters.
    if is_enabled:
        _disable_siblings(db, organization_id, kind, keep_id=None)

    row = NotificationProviderConfig(
        organization_id=organization_id,
        kind=kind,
        provider=provider,
        name=name.strip(),
        config=plain,
        secrets_encrypted=encrypt_secrets(secrets),
        is_enabled=is_enabled,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_config(
    db: Session,
    organization_id: uuid.UUID,
    config_id: uuid.UUID,
    *,
    name: str | None = None,
    config: dict | None = None,
    is_enabled: bool | None = None,
) -> NotificationProviderConfig:
    row = get_config(db, organization_id, config_id)
    if row.archived_at is not None:
        raise ProviderConfigError("This provider configuration has been archived")

    if name is not None:
        row.name = name.strip()

    if config is not None:
        plain, submitted_secrets = split_secrets(row.kind, row.provider, config)
        # Merge over what is stored so omitting a secret means "leave it alone", not "clear it" -
        # the API never returns secrets, so a round-tripped form cannot resend them.
        merged_secrets = {**decrypt_secrets(row.secrets_encrypted), **submitted_secrets}
        provider_class(row.kind, row.provider)({**plain, **merged_secrets})
        row.config = plain
        row.secrets_encrypted = encrypt_secrets(merged_secrets)

    if is_enabled is not None:
        if is_enabled:
            # Re-validate before enabling: a config saved as a draft must not become live
            # without proving it is at least structurally complete.
            instantiate(row.kind, row.provider, row.config, row.secrets_encrypted)
            _disable_siblings(db, organization_id, row.kind, keep_id=row.id)
        row.is_enabled = is_enabled

    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


def archive_config(db: Session, organization_id: uuid.UUID, config_id: uuid.UUID) -> NotificationProviderConfig:
    """Soft delete, matching the platform-wide convention. Archiving also disables, so removing
    a provider from the list cannot leave it quietly still handling mail."""
    row = get_config(db, organization_id, config_id)
    if row.archived_at is None:
        row.archived_at = datetime.now(timezone.utc)
        row.is_enabled = False
        row.updated_at = row.archived_at
        db.commit()
        db.refresh(row)
    return row


def test_config(db: Session, organization_id: uuid.UUID, config_id: uuid.UUID) -> tuple[bool, str]:
    """Run the provider's own verify() against the real remote end and remember the outcome.

    Never raises for a failed test - a broken tenant credential is an expected answer here, not
    a server error - so the caller always gets (ok, message) to render."""
    row = get_config(db, organization_id, config_id)
    try:
        provider = instantiate(row.kind, row.provider, row.config, row.secrets_encrypted)
        message = provider.verify()
        ok = True
    except (ProviderConfigError, ProviderSendError) as exc:
        message, ok = str(exc), False
    except Exception as exc:  # a transport can raise almost anything; never 500 on a test button
        message, ok = f"Unexpected error: {exc}", False

    row.last_test_at = datetime.now(timezone.utc)
    row.last_test_ok = ok
    row.last_test_message = message[:2000]
    db.commit()
    return ok, message
