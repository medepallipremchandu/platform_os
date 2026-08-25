import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Leaves room for a future "group" principal_type without a breaking migration (see
# app.core.constants.PrincipalType) - Groups are explicitly not implemented in this build.
PRINCIPAL_TYPES = ("user", "service_principal", "group")
SCOPE_TYPES = ("organization", "service")


class RoleAssignment(Base):
    """Binds a principal (user or service_principal - principal_id is polymorphic, so no FK)
    to a RoleDefinition at a Scope.

    scope_type="organization" -> scope_id = str(organization_id) (grants the role everywhere
        in that org).
    scope_type="service"      -> scope_id = "<organization_id>:<service_name>" (grants the
        role only within that one platform service - see app.core.constants.ServiceName).
    """

    __tablename__ = "role_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    principal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    principal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    role_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("role_definitions.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    role_definition: Mapped["RoleDefinition"] = relationship()  # noqa: F821
