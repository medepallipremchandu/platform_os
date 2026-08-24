"""Schemas the LLM's JSON output is validated against. Not exposed via the API directly."""
from pydantic import BaseModel, Field


class LLMRubric(BaseModel):
    name: str
    description: str
    weight_percentage: float = Field(ge=0, le=100)


class LLMSkill(BaseModel):
    name: str
    description: str
    rubrics: list[LLMRubric]


class LLMJDExtraction(BaseModel):
    job_title: str
    role_context: str
    job_context_summary: str
    responsibilities: list[str]
    qualifications: list[str]
    skills: list[LLMSkill]


class LLMResumeSkill(BaseModel):
    name: str
    years_experience: float | None = None
    proficiency: str | None = None  # beginner | intermediate | advanced | expert


class LLMWorkHistoryItem(BaseModel):
    company: str
    title: str
    start_date: str | None = None
    end_date: str | None = None
    description: str


class LLMEducationItem(BaseModel):
    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    graduation_year: str | None = None


class LLMResumeExtraction(BaseModel):
    candidate_name: str | None = None
    candidate_email: str | None = None
    candidate_phone: str | None = None
    total_experience_years: float | None = None
    summary: str
    skills: list[LLMResumeSkill]
    work_history: list[LLMWorkHistoryItem]
    education: list[LLMEducationItem]
    certifications: list[str]


class LLMSkillMatch(BaseModel):
    skill_name: str
    jd_weight_percentage: float = Field(ge=0, le=100)
    required_level: str
    candidate_evidence: str
    match_percentage: float = Field(ge=0, le=100)
    verdict: str  # e.g. "strong match", "partial match", "gap"


class LLMMatchAnalysis(BaseModel):
    overall_match_percentage: float = Field(ge=0, le=100)
    skill_matches: list[LLMSkillMatch]
    strengths: list[str]
    gaps: list[str]
    market_context_commentary: str
    recommendation: str
