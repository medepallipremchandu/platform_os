import uuid
from datetime import datetime

from sqlalchemy import DateTime, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ResumeAnalysis(Base):
    __tablename__ = "resume_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    resume_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # pdf | docx | doc
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)

    candidate_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    candidate_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    candidate_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    total_experience_years: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    skills: Mapped[list] = mapped_column(JSONB, default=list)  # [{name, years_experience, proficiency}]
    work_history: Mapped[list] = mapped_column(JSONB, default=list)  # [{company, title, start_date, end_date, description}]
    education: Mapped[list] = mapped_column(JSONB, default=list)  # [{institution, degree, field_of_study, graduation_year}]
    certifications: Mapped[list] = mapped_column(JSONB, default=list)  # [string]

    raw_llm_response: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    modified_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
