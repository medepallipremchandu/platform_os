import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

EMAIL_LOG_STATUSES = (
    "sent",
    "failed",
    "logged_no_smtp_configured",
    # The organization has its own queue provider enabled, so the dispatcher handed delivery off
    # to that broker instead of sending inline. A second EmailLog row is written by whichever
    # worker consumes from the tenant broker and actually delivers.
    "queued_to_org_queue",
)

PROVIDER_CONFIG_KINDS = ("email", "queue")


class EmailLog(Base):
    """One row per send attempt of app.tasks.deliver_email - the audit trail for every
    transactional email this service was asked to deliver, regardless of whether it was
    actually sent, failed, handed off to a tenant queue, or (with no email provider configured)
    only logged.

    `organization_id` is nullable because a password-reset request can arrive for an email
    address that belongs to no organization the producer could name."""

    __tablename__ = "email_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    to_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    template: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    # Which provider actually handled it ("smtp" / "sendgrid" / "console" / a queue provider on
    # a hand-off row), and whether that came from tenant config or the platform default. Both
    # are answers you want in an incident without re-deriving them from config history.
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider_scope: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "organization" | "platform"
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationProviderConfig(Base):
    """A tenant-supplied provider an organization plugs into this service - either an email
    provider (how their transactional mail is actually sent) or a queue provider (which broker
    their notifications are dispatched onto). One table for both because the lifecycle is
    identical (create / configure / enable / test / disable / archive) and the only thing that
    varies is which registry validates `config` - see app/providers/.

    Secrets never live in `config`. Each provider class declares which of its fields are secret;
    those are stripped out, Fernet-encrypted as one JSON blob into `secrets_encrypted`, and never
    returned by the API - the same write-only posture iam-service uses for service-principal
    secrets.

    At most one row per (organization_id, kind) may be enabled at a time; that is enforced both
    in the service layer and by a partial unique index (see the Alembic migration). An
    organization with no enabled row of a kind transparently falls back to the platform default,
    which is why this whole feature is additive and no existing organization changes behaviour."""

    __tablename__ = "notification_provider_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    secrets_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Result of the most recent POST .../test, kept so the console can show "last verified"
    # without the operator having to re-run a live test to remember the outcome.
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Soft delete, matching the platform-wide convention (iam-service archives role definitions
    # and revokes role assignments rather than deleting rows).
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


Index(
    "ix_notification_provider_configs_org_kind",
    NotificationProviderConfig.organization_id,
    NotificationProviderConfig.kind,
)

# The load-bearing constraint of the whole tenant-provider feature: at most ONE enabled provider
# per (organization, kind). The service layer disables siblings before enabling a replacement,
# but this index is what makes "two active SMTP relays" impossible rather than merely unlikely.
#
# Declared on the model as well as in the Alembic migration so that Base.metadata.create_all()
# - which is how the test database is built - produces the same schema production runs. It was
# missing here once, and the tests happily passed a case that failed against a migrated database.
Index(
    "uq_notification_provider_enabled_per_kind",
    NotificationProviderConfig.organization_id,
    NotificationProviderConfig.kind,
    unique=True,
    postgresql_where=text("is_enabled AND archived_at IS NULL"),
)
