"""initial schema

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
        "telephony_provider_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("phone_number", sa.String(length=32), nullable=False),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False),
        sa.Column("visibility", sa.String(length=16), nullable=False, server_default="organization"),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_telephony_provider_configs_organization_id", "telephony_provider_configs", ["organization_id"])

    op.create_table(
        "telephony_provider_config_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "provider_config_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("telephony_provider_configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(length=255), nullable=False),
    )
    op.create_index(
        "ix_telephony_provider_config_grants_provider_config_id",
        "telephony_provider_config_grants",
        ["provider_config_id"],
    )

    op.create_table(
        "call_agent_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("persona", sa.Text(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("consent_line", sa.Text(), nullable=False),
        sa.Column("closing_line", sa.Text(), nullable=False),
        sa.Column("fields", postgresql.JSONB(), nullable=False),
        sa.Column("max_conversation_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("retry_max_attempts", sa.Integer(), nullable=False),
        sa.Column("retry_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("retry_on_statuses", postgresql.JSONB(), nullable=False),
        sa.Column(
            "telephony_provider_config_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("telephony_provider_configs.id"),
            nullable=False,
        ),
        sa.Column("visibility", sa.String(length=16), nullable=False, server_default="organization"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_call_agent_configs_organization_id", "call_agent_configs", ["organization_id"])

    op.create_table(
        "call_agent_config_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "call_agent_config_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("call_agent_configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(length=255), nullable=False),
    )
    op.create_index(
        "ix_call_agent_config_grants_call_agent_config_id", "call_agent_config_grants", ["call_agent_config_id"]
    )

    op.create_table(
        "calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "call_agent_config_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("call_agent_configs.id"), nullable=True
        ),
        sa.Column(
            "telephony_provider_config_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("telephony_provider_configs.id"),
            nullable=False,
        ),
        sa.Column("to_number", sa.String(length=32), nullable=False),
        sa.Column("from_number", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="CREATED"),
        sa.Column("max_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("call_script", postgresql.JSONB(), nullable=False),
        sa.Column("webhook_url", sa.String(length=1024), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
        sa.Column("provider_call_sid", sa.String(length=64), nullable=True),
        sa.Column("extracted_fields", postgresql.JSONB(), nullable=False),
        sa.Column("consent_status", sa.String(length=16), nullable=True),
        sa.Column("end_reason", sa.String(length=64), nullable=True),
        sa.Column("silence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consent_retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warned_2min", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("warned_1min", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("retry_max_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_interval_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("retry_on_statuses", postgresql.JSONB(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("root_call_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("calls.id"), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_calls_organization_id", "calls", ["organization_id"])
    op.create_index("ix_calls_next_retry_at", "calls", ["next_retry_at"])

    op.create_table(
        "call_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("call_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_call_events_call_id_created_at", "call_events", ["call_id", "created_at"])

    op.create_table(
        "conversation_turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("call_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("call_id", "turn_index", name="uq_conversation_turn_call_id_turn_index"),
    )

    op.create_table(
        "call_summaries",
        sa.Column("call_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("calls.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("extracted_fields", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("call_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("calls.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "key", name="uq_org_idempotency_key"),
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.drop_table("call_summaries")
    op.drop_table("conversation_turns")
    op.drop_table("call_events")
    op.drop_table("calls")
    op.drop_table("call_agent_config_grants")
    op.drop_table("call_agent_configs")
    op.drop_table("telephony_provider_config_grants")
    op.drop_table("telephony_provider_configs")
