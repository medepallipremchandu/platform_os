import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class JDAnalysis(Base):
    __tablename__ = "jd_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jd_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    jd_text: Mapped[str] = mapped_column(Text, nullable=False)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_context_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsibilities: Mapped[list] = mapped_column(JSONB, default=list)
    qualifications: Mapped[list] = mapped_column(JSONB, default=list)
    raw_llm_response: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    modified_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    skills: Mapped[list["Skill"]] = relationship(
        back_populates="jd_analysis", cascade="all, delete-orphan", order_by="Skill.created_at"
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def skills_count(self) -> int:
        return len(self.skills)


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jd_analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jd_analyses.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    jd_analysis: Mapped["JDAnalysis"] = relationship(back_populates="skills")
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
