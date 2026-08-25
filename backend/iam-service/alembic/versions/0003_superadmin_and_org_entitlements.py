"""platform superadmin tier + per-organization permission entitlements

Adds:
  - users.is_superadmin - the platform tier that sits ABOVE organizations. Deliberately a
    boolean on the user, not a role or a permission: a superadmin has no organization
    membership, so there is no org scope for a RoleAssignment to hang off, and holding every
    talentos.iam.* permission inside some organization must never be equivalent to being a
    platform superadmin.
  - organizations.allowed_permissions - the entitlement CEILING a superadmin sets when creating
    an organization. NULL or empty means unrestricted, which is what keeps this migration
    backward-compatible: every organization that already exists keeps behaving exactly as it
    did, rather than being retroactively locked out of everything.
  - refresh_tokens.organization_id becomes nullable - a superadmin with no organization
    membership still needs a refresh token, and it belongs to no organization.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-25

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
    op.add_column("users", sa.Column("is_superadmin", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column("users", "is_superadmin", server_default=None)

    op.add_column("organizations", sa.Column("allowed_permissions", postgresql.JSONB(), nullable=True))

    op.alter_column("refresh_tokens", "organization_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)


def downgrade() -> None:
    op.alter_column("refresh_tokens", "organization_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.drop_column("organizations", "allowed_permissions")
    op.drop_column("users", "is_superadmin")
