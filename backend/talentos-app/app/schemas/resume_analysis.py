import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ResumeSkillOut(BaseModel):
    name: str
    years_experience: float | None = None
    proficiency: str | None = None


class WorkHistoryItemOut(BaseModel):
    company: str
    title: str
    start_date: str | None = None
    end_date: str | None = None
    description: str


class EducationItemOut(BaseModel):
    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    graduation_year: str | None = None


class ResumeAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resume_code: str
    original_filename: str
    file_type: str
    candidate_name: str | None
    candidate_email: str | None
    candidate_phone: str | None
    total_experience_years: float | None
    summary: str | None
    skills: list[ResumeSkillOut]
    work_history: list[WorkHistoryItemOut]
    education: list[EducationItemOut]
    certifications: list[str]

    created_by: str | None
    created_at: datetime
    modified_by: str | None
    modified_at: datetime | None
    deleted_by: str | None
    deleted_at: datetime | None
    is_deleted: bool


class ResumeAnalysisSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resume_code: str
    candidate_name: str | None
    total_experience_years: float | None
    created_by: str | None
    created_at: datetime
    modified_by: str | None
    modified_at: datetime | None
    is_deleted: bool
