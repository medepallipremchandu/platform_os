import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

AGENT_STATUSES = ("draft", "published")


class Agent(Base):
    """A user-authored, reusable AI task: a prompt template bound to a model, with limits.
    Callers never see the prompt or model directly - they hit /invoke with the agent's key."""

    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    agent_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    # names the template's {{placeholders}} expect, e.g. ["jd_text"] - drives both validation
    # and the "fill in variables" form when someone tests the agent.
    input_variables: Mapped[list] = mapped_column(JSONB, default=list)

    primary_model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("models.id"), nullable=False)
    fallback_model_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("models.id"), nullable=True
    )

    max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    timeout_seconds: Mapped[float] = mapped_column(nullable=False)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")

    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    primary_model: Mapped["Model"] = relationship(foreign_keys=[primary_model_id])  # noqa: F821
    fallback_model: Mapped["Model | None"] = relationship(foreign_keys=[fallback_model_id])  # noqa: F821
    credentials: Mapped[list["AgentCredential"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan", order_by="AgentCredential.created_at.desc()"
    )

    @property
    def is_published(self) -> bool:
        return self.status == "published"
