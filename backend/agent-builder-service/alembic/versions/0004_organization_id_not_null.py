"""make organization_id NOT NULL on models and agents

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-25

Run scripts/backfill_organization_id.py BEFORE this migration - it sets organization_id on
every existing row to the value read from .env's BOOTSTRAP_ORGANIZATION_ID. This migration
will fail loudly (NOT NULL violation) if any row was left unbackfilled, which is the point:
better to fail the migration than silently leave an unscoped row.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("models", "organization_id", nullable=False)
    op.alter_column("agents", "organization_id", nullable=False)


def downgrade() -> None:
    op.alter_column("agents", "organization_id", nullable=True)
    op.alter_column("models", "organization_id", nullable=True)
