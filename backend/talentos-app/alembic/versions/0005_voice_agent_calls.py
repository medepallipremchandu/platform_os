"""voice agent call config + submission call history

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jd_call_agent_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "jd_analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jd_analyses.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        # A voice-agent-service resource id, not a local foreign key - that resource lives in a
        # different service's database.
        sa.Column("call_agent_config_id", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "submission_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "submission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("submissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # voice-agent-service's own Call id - a UUID string, not a local foreign key, for the
        # same different-database reason as jd_call_agent_configs.call_agent_config_id above.
        sa.Column("voice_agent_call_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("summary_text", sa.Text(), nullable=True),
        # Cached alongside summary_text (both refreshed from GET /calls/{id}/summary once a call
        # is terminal) so the submission call panel can show extracted fields inline without a
        # second live-proxy endpoint - see app/models/voice_call.py docstring.
        sa.Column("extracted_fields", postgresql.JSONB(), nullable=True),
        sa.Column("end_reason", sa.String(length=100), nullable=True),
        sa.Column("triggered_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column("submission_calls", "status", server_default=None)
    op.alter_column("submission_calls", "attempt_number", server_default=None)
    op.create_index("ix_submission_calls_submission_id", "submission_calls", ["submission_id"])
    op.create_index("ix_submission_calls_voice_agent_call_id", "submission_calls", ["voice_agent_call_id"])


def downgrade() -> None:
    op.drop_table("submission_calls")
    op.drop_table("jd_call_agent_configs")
