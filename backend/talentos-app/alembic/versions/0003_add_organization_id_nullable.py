"""add organization_id (nullable) to top-level tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-25

Part 1 of 2 of the IAM organization-scoping migration: adds organization_id as nullable so
existing rows don't break, then scripts/backfill_organization_id.py stamps every existing row
with BOOTSTRAP_ORGANIZATION_ID, then 0004 makes the columns NOT NULL.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jd_analyses", sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_jd_analyses_organization_id", "jd_analyses", ["organization_id"])

    op.add_column("resume_analyses", sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_resume_analyses_organization_id", "resume_analyses", ["organization_id"])

    op.add_column("submissions", sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_submissions_organization_id", "submissions", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_submissions_organization_id", table_name="submissions")
    op.drop_column("submissions", "organization_id")

    op.drop_index("ix_resume_analyses_organization_id", table_name="resume_analyses")
    op.drop_column("resume_analyses", "organization_id")

    op.drop_index("ix_jd_analyses_organization_id", table_name="jd_analyses")
    op.drop_column("jd_analyses", "organization_id")
