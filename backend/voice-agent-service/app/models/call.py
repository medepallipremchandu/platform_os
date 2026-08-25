from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Call(Base):
    """One actual call attempt. `call_script` and the `retry_*` columns are SNAPSHOTS taken at
    creation time (from the CallAgentConfig, or supplied inline) so editing a CallAgentConfig
    later never changes an in-flight or historical call."""

    __tablename__ = "calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    call_agent_config_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("call_agent_configs.id"), nullable=True
    )
    telephony_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("telephony_provider_configs.id"), nullable=False
    )

    to_number: Mapped[str] = mapped_column(String(32), nullable=False)
    from_number: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="CREATED")

    max_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    # Snapshot of persona/objective/consent_line/closing_line/fields at creation time.
    call_script: Mapped[dict] = mapped_column(JSONB, nullable=False)

    webhook_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    provider_call_sid: Mapped[str | None] = mapped_column(String(64), nullable=True)

    extracted_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    consent_status: Mapped[str | None] = mapped_column(String(16), nullable=True)  # granted | denied | unclear
    end_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # In-call turn-loop bookkeeping (kept as dedicated columns, not folded into the tenant-facing
    # `metadata_json` above, so tenant-supplied metadata is never silently mutated by us).
    silence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consent_retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warned_2min: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    warned_1min: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Retry policy snapshot (from the CallAgentConfig at creation time, or the inline defaults -
    # retry_max_attempts=0 for a fully ad-hoc call, since there's no config to carry a policy).
    retry_max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    retry_on_statuses: Mapped[list] = mapped_column(JSONB, nullable=False, default=lambda: ["NO_ANSWER", "BUSY"])

    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    root_call_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("calls.id"), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    events: Mapped[list["CallEvent"]] = relationship(back_populates="call", cascade="all, delete-orphan")
    turns: Mapped[list["ConversationTurn"]] = relationship(back_populates="call", cascade="all, delete-orphan")
    summary: Mapped["CallSummary | None"] = relationship(back_populates="call", cascade="all, delete-orphan")


class CallEvent(Base):
    __tablename__ = "call_events"
    __table_args__ = (Index("ix_call_events_call_id_created_at", "call_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    call: Mapped["Call"] = relationship(back_populates="events")


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"
    # Unique, not just indexed: a duplicate Twilio webhook delivery for the same turn must fail
    # loudly (IntegrityError) rather than silently insert a second row for that turn.
    __table_args__ = (UniqueConstraint("call_id", "turn_index", name="uq_conversation_turn_call_id_turn_index"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(String(16), nullable=False)  # ai | callee
    text: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    call: Mapped["Call"] = relationship(back_populates="turns")


class CallSummary(Base):
    __tablename__ = "call_summaries"

    call_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), primary_key=True)
    summary_text: Mapped[str] = mapped_column(String, nullable=False)
    extracted_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    call: Mapped["Call"] = relationship(back_populates="summary")


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_org_idempotency_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    call_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calls.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
