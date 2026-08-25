import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

ACTOR_TYPES = ("user", "service_principal", "system")
AUDIT_RESULTS = ("success", "denied", "error")


class AuditLogEntry(Base):
    """Immutable, append-only record of every authn/authz decision and every business-data
    mutation platform-wide (design doc §8). No update/delete endpoint exists for this table."""

    __tablename__ = "audit_log_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    changes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
