import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

QUESTION_TYPES = ("descriptive", "mcq", "coding")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    question_type: Mapped[str] = mapped_column(String(20), nullable=False, default="descriptive")
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # MCQ-only
    options: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    correct_option_index: Mapped[int | None] = mapped_column(nullable=True)

    # Coding-only
    language: Mapped[str | None] = mapped_column(String(30), nullable=True)
    starter_code: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    skill: Mapped["Skill"] = relationship()  # noqa: F821
    rubric_maps: Mapped[list["QuestionRubricMap"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="QuestionRubricMap.created_at"
    )
    test_cases: Mapped[list["QuestionTestCase"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="QuestionTestCase.created_at"
    )


class QuestionRubricMap(Base):
    """Links a question to one or more rubrics with a weight (<=100 total per question)
    plus the evaluation criteria to apply for that rubric on that specific question."""

    __tablename__ = "question_rubric_maps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    rubric_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rubrics.id", ondelete="CASCADE"), nullable=False
    )
    weight_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    evaluation_criteria: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    question: Mapped["Question"] = relationship(back_populates="rubric_maps")
    rubric: Mapped["Rubric"] = relationship()  # noqa: F821

    @property
    def rubric_name(self) -> str:
        return self.rubric.name


class QuestionTestCase(Base):
    """A single input/expected-output pair for a CODING question."""

    __tablename__ = "question_test_cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    input: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    question: Mapped["Question"] = relationship(back_populates="test_cases")
