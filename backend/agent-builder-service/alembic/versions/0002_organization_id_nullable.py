"""add organization_id (nullable) to models and agents

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-25

Nullable for now - backfilled by scripts/backfill_organization_id.py, then tightened to
NOT NULL by migration 0004. Every existing row is scoped to the org read from .env's
BOOTSTRAP_ORGANIZATION_ID by that script, not hardcoded here.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("models", sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_models_organization_id", "models", ["organization_id"])

    op.add_column("agents", sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_agents_organization_id", "agents", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_agents_organization_id", table_name="agents")
    op.drop_column("agents", "organization_id")

    op.drop_index("ix_models_organization_id", table_name="models")
    op.drop_column("models", "organization_id")
