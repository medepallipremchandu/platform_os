"""make organization_id NOT NULL on top-level tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-25

Part 2 of 2 of the IAM organization-scoping migration. Run scripts/backfill_organization_id.py
between 0003 and this one - it fails loudly (via this ALTER COLUMN) if any row was left
without an organization_id.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("jd_analyses", "organization_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.alter_column("resume_analyses", "organization_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.alter_column("submissions", "organization_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)


def downgrade() -> None:
    op.alter_column("jd_analyses", "organization_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.alter_column("resume_analyses", "organization_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.alter_column("submissions", "organization_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
