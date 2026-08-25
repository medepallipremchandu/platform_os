import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ServicePrincipal(Base):
    """Non-human identity for machine-to-machine calls. Two flavors distinguished by
    resource_type/resource_id being null (a generic service-to-service credential) or set
    (a resource-bound credential, e.g. one specific agent-builder-service agent's invoke
    credential - see design doc §6). The secret is shown once at creation/rotation and
    stored only as a SHA-256 hash (app.core.secrets)."""

    __tablename__ = "service_principals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped["Organization"] = relationship()  # noqa: F821

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None
