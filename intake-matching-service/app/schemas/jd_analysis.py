import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class JDAnalysisRequest(BaseModel):
    jd_text: str = Field(min_length=20, description="Full job description text to analyze.")


class JDAnalysisUpdateRequest(BaseModel):
    """All fields optional - only the ones provided are changed (and diffed into the audit log)."""

    job_title: str | None = None
    role_context: str | None = None
    job_context_summary: str | None = None
    responsibilities: list[str] | None = None
    qualifications: list[str] | None = None


class RubricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    weight_percentage: float


class SkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    rubrics: list[RubricOut]


class JDAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    jd_code: str
    job_title: str | None
    role_context: str | None
    job_context_summary: str | None
    responsibilities: list[str]
    qualifications: list[str]
    skills: list[SkillOut]

    created_by: str | None
    created_at: datetime
    modified_by: str | None
    modified_at: datetime | None
    deleted_by: str | None
    deleted_at: datetime | None
    is_deleted: bool


class JDAnalysisSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    jd_code: str
    job_title: str | None
    skills_count: int
    created_by: str | None
    created_at: datetime
    modified_by: str | None
    modified_at: datetime | None
    is_deleted: bool
