import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Submission(Base):
    """Pairs one JD analysis with one resume analysis - the unit a match analysis and,
    downstream, an assessment-service interview session are built from."""

    __tablename__ = "submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    jd_analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jd_analyses.id", ondelete="CASCADE"), nullable=False
    )
    resume_analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resume_analyses.id", ondelete="CASCADE"), nullable=False
    )

    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    modified_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    jd_analysis: Mapped["JDAnalysis"] = relationship()  # noqa: F821
    resume_analysis: Mapped["ResumeAnalysis"] = relationship()  # noqa: F821
    match_analysis: Mapped["MatchAnalysis | None"] = relationship(
        back_populates="submission", cascade="all, delete-orphan", uselist=False
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class MatchAnalysis(Base):
    """The LLM's assessment of how well a candidate's resume matches a JD - skill-by-skill
    breakdown, strengths/gaps, and market-context commentary."""

    __tablename__ = "match_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    overall_match_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    skill_matches: Mapped[list] = mapped_column(JSONB, default=list)
    # [{skill_name, jd_weight_percentage, required_level, candidate_evidence, match_percentage, verdict}]
    strengths: Mapped[list] = mapped_column(JSONB, default=list)  # [string]
    gaps: Mapped[list] = mapped_column(JSONB, default=list)  # [string]
    market_context_commentary: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_llm_response: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    submission: Mapped["Submission"] = relationship(back_populates="match_analysis")
