import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvaluationRequest(BaseModel):
    question_id: uuid.UUID
    # exactly one of these must be set, matching the question's question_type
    candidate_answer: str | None = Field(default=None, description="Descriptive: free-text answer")
    selected_option_index: int | None = Field(default=None, description="MCQ: 0-based chosen option index")
    candidate_code: str | None = Field(default=None, description="Coding: submitted source code")

    @model_validator(mode="after")
    def _exactly_one_answer_shape(self) -> "EvaluationRequest":
        provided = [
            v is not None for v in (self.candidate_answer, self.selected_option_index, self.candidate_code)
        ]
        if sum(provided) != 1:
            raise ValueError(
                "Provide exactly one of candidate_answer, selected_option_index, or candidate_code"
            )
        return self


class RubricScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rubric_id: uuid.UUID
    rubric_name: str
    expected_weight_percentage: float
    achieved_score_percentage: float
    weighted_contribution: float
    feedback: str | None


class TestCaseResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    input: str
    expected_output: str
    actual_output: str
    passed: bool
    is_hidden: bool
    stderr: str | None
    execution_time_ms: float | None


class EvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question_id: uuid.UUID
    candidate_answer: str | None
    selected_option_index: int | None
    candidate_code: str | None
    overall_score_percentage: float
    summary: str | None
    rubric_scores: list[RubricScoreOut]
    test_case_results: list[TestCaseResultOut] = []
    created_at: datetime


class SubmitBatchRequest(BaseModel):
    answers: list[EvaluationRequest] = Field(min_length=1)


class SkillScoreOut(BaseModel):
    skill_id: uuid.UUID
    skill_name: str
    average_score_percentage: float
    question_count: int


class BatchEvaluationResponse(BaseModel):
    overall_score_percentage: float
    evaluations: list[EvaluationResponse]
    skill_scores: list[SkillScoreOut]
