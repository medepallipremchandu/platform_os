import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class JDCallAgentConfig(Base):
    """Which voice-agent-service call-agent config (script + retry policy) a JD's candidates get
    screened with, and whether AI phone screening is turned on for this JD at all. One row per
    JD - `call_agent_config_id` is a UUID string, NOT a local foreign key, because that resource
    lives in voice-agent-service's own database, not this one."""

    __tablename__ = "jd_call_agent_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jd_analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jd_analyses.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    call_agent_config_id: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    jd_analysis: Mapped["JDAnalysis"] = relationship()  # noqa: F821


class SubmissionCall(Base):
    """One AI phone-screen attempt against a submission's candidate. `voice_agent_call_id` is
    voice-agent-service's own Call id (a UUID string, not a local FK, for the same
    different-database reason as JDCallAgentConfig above). `status`/`end_reason` are a cache of
    voice-agent-service's own source of truth, refreshed via the webhook receiver
    (app/api/webhooks.py) and lazily on read (app/services/voice_call_service.py) - never
    trusted from anywhere else.

    `extracted_fields` is one field beyond the original spec's list: it caches
    GET /calls/{id}/summary's `extracted_fields` alongside `summary_text` (same refresh path, same
    "terminal call" trigger) so the submission's call panel can show extracted fields inline
    without a second live-proxy endpoint - see README for this call."""

    __tablename__ = "submission_calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    voice_agent_call_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    triggered_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    submission: Mapped["Submission"] = relationship()  # noqa: F821
