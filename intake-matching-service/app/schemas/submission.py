import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.jd_analysis import SkillOut


class SubmissionCreateRequest(BaseModel):
    jd_analysis_id: uuid.UUID
    resume_analysis_id: uuid.UUID


class SkillMatchOut(BaseModel):
    skill_name: str
    jd_weight_percentage: float
    required_level: str
    candidate_evidence: str
    match_percentage: float
    verdict: str


class MatchAnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    overall_match_percentage: float
    skill_matches: list[SkillMatchOut]
    strengths: list[str]
    gaps: list[str]
    market_context_commentary: str | None
    recommendation: str | None
    created_at: datetime


class SubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    submission_code: str
    jd_analysis_id: uuid.UUID
    resume_analysis_id: uuid.UUID
    match_analysis: MatchAnalysisOut | None

    created_by: str | None
    created_at: datetime
    modified_by: str | None
    modified_at: datetime | None
    deleted_by: str | None
    deleted_at: datetime | None
    is_deleted: bool


class SubmissionSummary(BaseModel):
    id: uuid.UUID
    submission_code: str
    jd_code: str
    job_title: str | None
    resume_code: str
    candidate_name: str | None
    overall_match_percentage: float | None
    created_by: str | None
    created_at: datetime
    is_deleted: bool


class SubmissionForAssessment(BaseModel):
    """The service-to-service contract assessment-service calls to snapshot what it needs
    to run an interview for this submission."""

    submission_id: uuid.UUID
    submission_code: str
    jd_code: str
    job_title: str | None
    resume_code: str
    candidate_name: str | None
    skills: list[SkillOut]
