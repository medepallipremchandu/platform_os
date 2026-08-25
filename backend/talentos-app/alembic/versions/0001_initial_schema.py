"""initial schema

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
    op.execute("CREATE SEQUENCE jd_code_seq START 1")
    op.execute("CREATE SEQUENCE resume_code_seq START 1")
    op.execute("CREATE SEQUENCE submission_code_seq START 1")

    op.create_table(
        "jd_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("jd_code", sa.String(length=20), nullable=False, unique=True),
        sa.Column("jd_text", sa.Text(), nullable=False),
        sa.Column("job_title", sa.String(length=255), nullable=True),
        sa.Column("role_context", sa.Text(), nullable=True),
        sa.Column("job_context_summary", sa.Text(), nullable=True),
        sa.Column("responsibilities", postgresql.JSONB(), nullable=False),
        sa.Column("qualifications", postgresql.JSONB(), nullable=False),
        sa.Column("raw_llm_response", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(length=255), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "jd_analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jd_analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_skills_jd_analysis_id", "skills", ["jd_analysis_id"])

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
        "resume_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("resume_code", sa.String(length=20), nullable=False, unique=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=10), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("candidate_name", sa.String(length=255), nullable=True),
        sa.Column("candidate_email", sa.String(length=255), nullable=True),
        sa.Column("candidate_phone", sa.String(length=50), nullable=True),
        sa.Column("total_experience_years", sa.Numeric(4, 1), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("skills", postgresql.JSONB(), nullable=False),
        sa.Column("work_history", postgresql.JSONB(), nullable=False),
        sa.Column("education", postgresql.JSONB(), nullable=False),
        sa.Column("certifications", postgresql.JSONB(), nullable=False),
        sa.Column("raw_llm_response", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(length=255), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("submission_code", sa.String(length=20), nullable=False, unique=True),
        sa.Column(
            "jd_analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jd_analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "resume_analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("resume_analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(length=255), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_submissions_jd_analysis_id", "submissions", ["jd_analysis_id"])
    op.create_index("ix_submissions_resume_analysis_id", "submissions", ["resume_analysis_id"])

    op.create_table(
        "match_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "submission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("submissions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("overall_match_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("skill_matches", postgresql.JSONB(), nullable=False),
        sa.Column("strengths", postgresql.JSONB(), nullable=False),
        sa.Column("gaps", postgresql.JSONB(), nullable=False),
        sa.Column("market_context_commentary", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("raw_llm_response", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("changed_by", sa.String(length=255), nullable=False),
        sa.Column("changes", postgresql.JSONB(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("match_analyses")
    op.drop_table("submissions")
    op.drop_table("resume_analyses")
    op.drop_table("rubrics")
    op.drop_table("skills")
    op.drop_table("jd_analyses")
    op.execute("DROP SEQUENCE submission_code_seq")
    op.execute("DROP SEQUENCE resume_code_seq")
    op.execute("DROP SEQUENCE jd_code_seq")
