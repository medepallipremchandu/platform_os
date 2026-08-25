import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.jd_analysis import SkillOut


class InterviewSessionCreateRequest(BaseModel):
    submission_id: uuid.UUID


class InterviewSessionResponse(BaseModel):
    id: uuid.UUID
    submission_id: uuid.UUID
    submission_code: str
    jd_code: str
    job_title: str | None
    resume_code: str
    candidate_name: str | None
    skills: list[SkillOut]
    created_by: str | None
    created_at: datetime


class InterviewSessionSummary(BaseModel):
    id: uuid.UUID
    submission_id: uuid.UUID
    submission_code: str
    jd_code: str
    job_title: str | None
    resume_code: str
    candidate_name: str | None
    created_at: datetime
