"""initial schema (interview-session based, post service split)

Revision ID: 0001
Revises:
Create Date: 2026-08-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interview_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("submission_code", sa.String(length=20), nullable=False),
        sa.Column("jd_code", sa.String(length=20), nullable=False),
        sa.Column("job_title", sa.String(length=255), nullable=True),
        sa.Column("resume_code", sa.String(length=20), nullable=False),
        sa.Column("candidate_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "interview_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_skills_interview_session_id", "skills", ["interview_session_id"])

    op.create_table(
        "rubrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "skill_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("weight_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_rubrics_skill_id", "rubrics", ["skill_id"])

    op.create_table(
        "questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "skill_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("question_type", sa.String(length=20), nullable=False, server_default="descriptive"),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.String(length=50), nullable=True),
        sa.Column("options", postgresql.JSONB(), nullable=True),
        sa.Column("correct_option_index", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(length=30), nullable=True),
        sa.Column("starter_code", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.alter_column("questions", "question_type", server_default=None)
    op.create_index("ix_questions_skill_id", "questions", ["skill_id"])

    op.create_table(
        "question_rubric_maps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "rubric_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rubrics.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("weight_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("evaluation_criteria", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_question_rubric_maps_question_id", "question_rubric_maps", ["question_id"])
    op.create_index("ix_question_rubric_maps_rubric_id", "question_rubric_maps", ["rubric_id"])

    op.create_table(
        "question_test_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("input", sa.Text(), nullable=False),
        sa.Column("expected_output", sa.Text(), nullable=False),
        sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_question_test_cases_question_id", "question_test_cases", ["question_id"])

    op.create_table(
        "evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("candidate_answer", sa.Text(), nullable=True),
        sa.Column("selected_option_index", sa.Integer(), nullable=True),
        sa.Column("candidate_code", sa.Text(), nullable=True),
        sa.Column("overall_score_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evaluations_question_id", "evaluations", ["question_id"])

    op.create_table(
        "evaluation_rubric_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "evaluation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_rubric_map_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("question_rubric_maps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "rubric_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rubrics.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("expected_weight_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("achieved_score_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("weighted_contribution", sa.Numeric(5, 2), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evaluation_rubric_scores_evaluation_id", "evaluation_rubric_scores", ["evaluation_id"])

    op.create_table(
        "evaluation_test_case_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "evaluation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_test_case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("question_test_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("input", sa.Text(), nullable=False),
        sa.Column("expected_output", sa.Text(), nullable=False),
        sa.Column("actual_output", sa.Text(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("stderr", sa.Text(), nullable=True),
        sa.Column("execution_time_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_evaluation_test_case_results_evaluation_id", "evaluation_test_case_results", ["evaluation_id"]
    )


def downgrade() -> None:
    op.drop_table("evaluation_test_case_results")
    op.drop_table("evaluation_rubric_scores")
    op.drop_table("evaluations")
    op.drop_table("question_test_cases")
    op.drop_table("question_rubric_maps")
    op.drop_table("questions")
    op.drop_table("rubrics")
    op.drop_table("skills")
    op.drop_table("interview_sessions")
