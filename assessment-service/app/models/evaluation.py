import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )

    # exactly one of these is populated, matching the question's question_type
    candidate_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_option_index: Mapped[int | None] = mapped_column(nullable=True)
    candidate_code: Mapped[str | None] = mapped_column(Text, nullable=True)

    overall_score_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    question: Mapped["Question"] = relationship()  # noqa: F821
    rubric_scores: Mapped[list["EvaluationRubricScore"]] = relationship(
        back_populates="evaluation", cascade="all, delete-orphan", order_by="EvaluationRubricScore.created_at"
    )
    test_case_results: Mapped[list["EvaluationTestCaseResult"]] = relationship(
        back_populates="evaluation", cascade="all, delete-orphan", order_by="EvaluationTestCaseResult.created_at"
    )


class EvaluationRubricScore(Base):
    __tablename__ = "evaluation_rubric_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False
    )
    question_rubric_map_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("question_rubric_maps.id", ondelete="CASCADE"), nullable=False
    )
    rubric_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rubrics.id", ondelete="CASCADE"), nullable=False
    )
    expected_weight_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    achieved_score_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    weighted_contribution: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    evaluation: Mapped["Evaluation"] = relationship(back_populates="rubric_scores")
    rubric: Mapped["Rubric"] = relationship()  # noqa: F821

    @property
    def rubric_name(self) -> str:
        return self.rubric.name


class EvaluationTestCaseResult(Base):
    """Per-test-case outcome of executing a candidate's code submission for a CODING question."""

    __tablename__ = "evaluation_test_case_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False
    )
    question_test_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("question_test_cases.id", ondelete="CASCADE"), nullable=False
    )
    input: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)
    actual_output: Mapped[str] = mapped_column(Text, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    evaluation: Mapped["Evaluation"] = relationship(back_populates="test_case_results")
