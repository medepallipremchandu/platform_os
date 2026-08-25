import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RoleDefinition(Base):
    """Named set of permissions. organization_id NULL = a global built-in role, seeded once
    and visible to every organization (is_builtin=True, cannot be edited/deleted via the
    API). organization_id set = a custom role authored by and owned by that org
    (is_builtin=False).

    A custom role is never hard-deleted - `archived_at` (soft delete) marks it retired instead.
    Archived roles are excluded from `GET /role-definitions` by default and can no longer be
    used in a new RoleAssignment, but existing assignments (and this row itself, for audit/
    history purposes) are left alone."""

    __tablename__ = "role_definitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    permissions: Mapped[list["Permission"]] = relationship(  # noqa: F821
        secondary="role_definition_permissions", viewonly=True
    )

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None


# Role names are unique per owner, and "no owner" (a global built-in) is its own namespace. A
# plain UNIQUE(organization_id, name) would not enforce the built-in case, because Postgres
# treats NULLs as distinct - two built-ins could both be called "Viewer". Hence two partial
# unique indexes.
#
# Declared here as well as in the Alembic migration so Base.metadata.create_all() - which is how
# the test database is built - produces the same schema production runs. Migration-only
# constraints are a trap this repo has already been bitten by once: a rule that exists in
# production but not under test lets a violating case pass CI and fail live.
Index(
    "uq_role_definitions_builtin_name",
    RoleDefinition.name,
    unique=True,
    postgresql_where=text("organization_id IS NULL"),
)
Index(
    "uq_role_definitions_org_name",
    RoleDefinition.organization_id,
    RoleDefinition.name,
    unique=True,
    postgresql_where=text("organization_id IS NOT NULL"),
)
