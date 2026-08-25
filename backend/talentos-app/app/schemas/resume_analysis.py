import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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


class ResumeAnalysisUpdateRequest(BaseModel):
    """All fields optional - only the ones provided are changed (and diffed into the audit log).

    Deliberately limited to the scalar profile fields a recruiter would plausibly need to correct
    after OCR/extraction errors (a misread name, a transposed digit in a phone number, etc). Not
    exposed here: `raw_text`/`raw_llm_response` (source-of-truth extraction inputs, not editable
    facts) and the structured `skills`/`work_history`/`education`/`certifications` lists (each is
    a list of nested objects sourced straight from the resume; hand-editing that structure safely
    needs its own item-level endpoints, which weren't in scope for this pass)."""

    candidate_name: str | None = Field(default=None, max_length=255)
    candidate_email: str | None = Field(default=None, max_length=255)
    candidate_phone: str | None = Field(default=None, max_length=50)
    total_experience_years: float | None = Field(default=None, ge=0, le=99.9)
    summary: str | None = None


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
