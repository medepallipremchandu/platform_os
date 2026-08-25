import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AgentCredential(Base):
    """A reference to an iam-service ServicePrincipal that is this agent's invoke credential
    (design doc §6: a resource-bound, per-agent Service Principal). No secret is ever stored
    here - iam-service hashes and owns the client_secret; this row only remembers which
    ServicePrincipal backs this agent and its (safe-to-display) client_id, so /agents/{id}/keys
    can list it without ever holding anything sensitive.

    Revoking sets revoked_at instead of deleting, preserving the invocation log's audit trail.
    """

    __tablename__ = "agent_credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    service_principal_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    agent: Mapped["Agent"] = relationship(back_populates="credentials")  # noqa: F821

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None
