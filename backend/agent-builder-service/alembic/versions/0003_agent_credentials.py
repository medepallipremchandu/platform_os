"""repurpose agent_api_keys into agent_credentials (IAM-backed credential reference)

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-25

The local key_hash/key_preview generation scheme is retired: an agent's invoke credential is
now a reference to an iam-service ServicePrincipal (service_principal_id, client_id) minted at
publish time (design doc §6). No secret is ever stored here - iam-service hashes and owns the
client_secret.

This is a structural/behavioral change, not a data migration - any existing agtk_... keys stop
being valid invoke credentials (agents must be re-published, or have their credential
regenerated, to get an IAM-issued one). That's expected and matches the migration plan's
"re-issued once, same one-time-reveal UX as today" (design doc §13 step 2).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("agent_api_keys", "agent_credentials")
    op.drop_constraint("agent_api_keys_key_hash_key", "agent_credentials", type_="unique")
    op.drop_column("agent_credentials", "key_hash")
    op.drop_column("agent_credentials", "key_preview")
    op.add_column("agent_credentials", sa.Column("service_principal_id", sa.String(length=64), nullable=True))
    op.add_column("agent_credentials", sa.Column("client_id", sa.String(length=64), nullable=True))
    # Existing rows (if any) have no corresponding ServicePrincipal - drop them rather than
    # leave unusable credential rows behind; the owning agent's is_published/publish flow
    # will re-mint a real one on next publish/regenerate.
    op.execute("DELETE FROM agent_credentials")
    op.alter_column("agent_credentials", "service_principal_id", nullable=False)
    op.alter_column("agent_credentials", "client_id", nullable=False)
    op.create_unique_constraint(
        "agent_credentials_service_principal_id_key", "agent_credentials", ["service_principal_id"]
    )
    op.drop_index("ix_agent_api_keys_agent_id", table_name="agent_credentials")
    op.create_index("ix_agent_credentials_agent_id", "agent_credentials", ["agent_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_credentials_agent_id", table_name="agent_credentials")
    op.create_index("ix_agent_api_keys_agent_id", "agent_credentials", ["agent_id"])
    op.drop_constraint("agent_credentials_service_principal_id_key", "agent_credentials", type_="unique")
    op.execute("DELETE FROM agent_credentials")
    op.drop_column("agent_credentials", "client_id")
    op.drop_column("agent_credentials", "service_principal_id")
    op.add_column("agent_credentials", sa.Column("key_preview", sa.String(length=20), nullable=False))
    op.add_column("agent_credentials", sa.Column("key_hash", sa.String(length=64), nullable=False))
    op.create_unique_constraint("agent_api_keys_key_hash_key", "agent_credentials", ["key_hash"])
    op.rename_table("agent_credentials", "agent_api_keys")
