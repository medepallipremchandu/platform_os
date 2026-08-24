import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InterviewSessionCreateRequest(BaseModel):
    submission_id: uuid.UUID


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


class InterviewSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    submission_id: uuid.UUID
    submission_code: str
    jd_code: str
    job_title: str | None
    resume_code: str
    candidate_name: str | None
    skills: list[SkillOut]
    created_at: datetime


class InterviewSessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    submission_id: uuid.UUID
    submission_code: str
    jd_code: str
    job_title: str | None
    resume_code: str
    candidate_name: str | None
    created_at: datetime
