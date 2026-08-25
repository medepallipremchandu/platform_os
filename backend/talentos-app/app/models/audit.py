import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    """Generic change history, shared across JDAnalysis/ResumeAnalysis/Submission - one row per
    create/update/delete, keyed by (entity_type, entity_id)."""

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_entity", "entity_type", "entity_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # created | updated | deleted
    changed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    changes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # {field: {old, new}}
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
