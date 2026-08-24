import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class InterviewSession(Base):
    """Owned entirely by assessment-service. Created from a one-time snapshot of the
    intake-matching-service's submission (job title, candidate name, skills/rubrics) fetched
    over HTTP - assessment-service never queries that service's database directly."""

    __tablename__ = "interview_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    submission_code: Mapped[str] = mapped_column(String(20), nullable=False)
    jd_code: Mapped[str] = mapped_column(String(20), nullable=False)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resume_code: Mapped[str] = mapped_column(String(20), nullable=False)
    candidate_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    skills: Mapped[list["Skill"]] = relationship(
        back_populates="interview_session", cascade="all, delete-orphan", order_by="Skill.created_at"
    )


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interview_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    interview_session: Mapped["InterviewSession"] = relationship(back_populates="skills")
    rubrics: Mapped[list["Rubric"]] = relationship(
        back_populates="skill", cascade="all, delete-orphan", order_by="Rubric.created_at"
    )


class Rubric(Base):
    """A weighted evaluation dimension for a skill. Weights sum to ~100 per skill."""

    __tablename__ = "rubrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    skill: Mapped["Skill"] = relationship(back_populates="rubrics")
