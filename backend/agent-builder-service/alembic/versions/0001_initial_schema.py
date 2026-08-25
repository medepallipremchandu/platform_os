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
    op.execute("CREATE SEQUENCE model_code_seq START 1")
    op.execute("CREATE SEQUENCE agent_code_seq START 1")

    op.create_table(
        "models",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("model_code", sa.String(length=20), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("model_id", sa.String(length=255), nullable=False),
        sa.Column("endpoint", sa.String(length=500), nullable=True),
        sa.Column("api_version", sa.String(length=50), nullable=True),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_code", sa.String(length=20), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt_template", sa.Text(), nullable=False),
        sa.Column("input_variables", postgresql.JSONB(), nullable=False),
        sa.Column("primary_model_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("models.id"), nullable=False),
        sa.Column("fallback_model_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("models.id"), nullable=True),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Float(), nullable=False),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column("agents", "status", server_default=None)

    op.create_table(
        "agent_api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("key_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("key_preview", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_api_keys_agent_id", "agent_api_keys", ["agent_id"])

    op.create_table(
        "agent_invocation_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("input_variables", postgresql.JSONB(), nullable=False),
        sa.Column("output_preview", sa.Text(), nullable=True),
        sa.Column("provider_used", sa.String(length=30), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agent_invocation_logs_agent_id_created_at", "agent_invocation_logs", ["agent_id", "created_at"])


def downgrade() -> None:
    op.drop_table("agent_invocation_logs")
    op.drop_table("agent_api_keys")
    op.drop_table("agents")
    op.drop_table("models")
    op.execute("DROP SEQUENCE agent_code_seq")
    op.execute("DROP SEQUENCE model_code_seq")
