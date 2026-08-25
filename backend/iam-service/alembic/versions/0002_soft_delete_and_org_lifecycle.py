"""soft-delete for role definitions/assignments + organization lifecycle

Adds:
  - organizations.is_active (deactivate, never hard-delete a tenant root)
  - role_definitions.archived_at (soft delete for custom roles)
  - role_assignments.revoked_at (soft delete - the security-critical one: see
    app.services.permission_service.resolve_permissions, which filters on this column)

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.alter_column("organizations", "is_active", server_default=None)

    op.add_column("role_definitions", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("role_assignments", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("role_assignments", "revoked_at")
    op.drop_column("role_definitions", "archived_at")
    op.drop_column("organizations", "is_active")
