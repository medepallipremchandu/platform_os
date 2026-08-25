"""initial notification-service schema

Two tables in talentos_notifications:

  - email_logs                      one row per email, the delivery audit trail
  - notification_provider_configs   an organization's own email / queue providers

Note what this migration does NOT create: the Kombu broker tables (`kombu_queue`,
`kombu_message`). Kombu's SQLAlchemy transport creates those itself on first connect, in this
same database. They are broker internals, not application schema, and letting Alembic own them
would mean this service's migrations fighting a library over tables it manages.

Revision ID: 0001
Revises:
Create Date: 2026-08-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("to_email", sa.String(length=320), nullable=False),
        sa.Column("template", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=True),
        sa.Column("provider_scope", sa.String(length=20), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_email_logs_to_email", "email_logs", ["to_email"])
    op.create_index("ix_email_logs_organization_id", "email_logs", ["organization_id"])

    op.create_table(
        "notification_provider_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("secrets_encrypted", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_ok", sa.Boolean(), nullable=True),
        sa.Column("last_test_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notification_provider_configs_organization_id", "notification_provider_configs", ["organization_id"])
    op.create_index("ix_notification_provider_configs_org_kind", "notification_provider_configs", ["organization_id", "kind"])

    # The load-bearing constraint of the whole tenant-provider feature: at most ONE enabled
    # provider per (organization, kind). The service layer disables siblings when enabling, but
    # a partial unique index is what makes "two active SMTP configs" impossible rather than
    # merely unlikely under a concurrent write.
    op.create_index(
        "uq_notification_provider_enabled_per_kind",
        "notification_provider_configs",
        ["organization_id", "kind"],
        unique=True,
        postgresql_where=sa.text("is_enabled AND archived_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_notification_provider_enabled_per_kind", table_name="notification_provider_configs")
    op.drop_index("ix_notification_provider_configs_org_kind", table_name="notification_provider_configs")
    op.drop_index("ix_notification_provider_configs_organization_id", table_name="notification_provider_configs")
    op.drop_table("notification_provider_configs")
    op.drop_index("ix_email_logs_organization_id", table_name="email_logs")
    op.drop_index("ix_email_logs_to_email", table_name="email_logs")
    op.drop_table("email_logs")
