import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AgentInvocationLog(Base):
    """One row per /invoke call - the audit trail an enterprise deployment needs for usage
    tracking, debugging, and (later) billing/rate-limit enforcement."""

    __tablename__ = "agent_invocation_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    input_variables: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_used: Mapped[str | None] = mapped_column(String(30), nullable=True)  # which model actually served it
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agent: Mapped["Agent"] = relationship()  # noqa: F821
