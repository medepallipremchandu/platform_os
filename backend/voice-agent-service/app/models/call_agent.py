from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CallAgentConfig(Base):
    """A reusable "script + retry policy + which provider" bundle. Editing this later never
    changes an in-flight or historical Call - every Call snapshots the script/retry policy it
    was created with (see app/models/call.Call.call_script / retry_* columns)."""

    __tablename__ = "call_agent_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    persona: Mapped[str] = mapped_column(String, nullable=False)
    objective: Mapped[str] = mapped_column(String, nullable=False)
    consent_line: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="This call may be recorded and is conducted by an AI assistant. Do you consent to continue?",
    )
    closing_line: Mapped[str] = mapped_column(String, nullable=False, default="Thanks for your time, have a great day!")
    fields: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # [{name, type, description}]

    max_conversation_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    retry_max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    retry_on_statuses: Mapped[list] = mapped_column(JSONB, nullable=False, default=lambda: ["NO_ANSWER", "BUSY"])

    telephony_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("telephony_provider_configs.id"), nullable=False
    )

    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="organization")  # organization | restricted
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    grants: Mapped[list["CallAgentConfigGrant"]] = relationship(
        back_populates="call_agent_config", cascade="all, delete-orphan"
    )


class CallAgentConfigGrant(Base):
    """Only rows exist when the parent CallAgentConfig.visibility == 'restricted'."""

    __tablename__ = "call_agent_config_grants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_agent_config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("call_agent_configs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)

    call_agent_config: Mapped["CallAgentConfig"] = relationship(back_populates="grants")
