import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.evaluation import TestCaseResultOut


class QuestionGenerateRequest(BaseModel):
    skill_id: uuid.UUID
    num_questions: int = Field(ge=1, le=10, description="How many questions to generate for this skill.")
    question_type: str = Field(default="descriptive", pattern="^(descriptive|mcq|coding)$")


class QuestionGenerateBatchItem(BaseModel):
    skill_id: uuid.UUID
    num_questions: int = Field(ge=1, le=10)
    question_type: str = Field(default="descriptive", pattern="^(descriptive|mcq|coding)$")


class QuestionGenerateBatchRequest(BaseModel):
    configs: list[QuestionGenerateBatchItem] = Field(min_length=1)


class RubricMapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rubric_id: uuid.UUID
    rubric_name: str
    weight_percentage: float
    evaluation_criteria: str


class QuestionTestCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    input: str
    expected_output: str
    is_hidden: bool


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question_type: str
    question_text: str
    difficulty: str | None
    created_at: datetime
    rubric_maps: list[RubricMapOut]

    options: list[str] | None = None
    correct_option_index: int | None = None

    language: str | None = None
    starter_code: str | None = None
    test_cases: list[QuestionTestCaseOut] = []


class QuestionGenerateResponse(BaseModel):
    skill_id: uuid.UUID
    skill_name: str
    questions: list[QuestionOut]


class RunCodeRequest(BaseModel):
    code: str = Field(min_length=1)
    scope: str = Field(default="sample", pattern="^(sample|visible)$")


class RunCodeResponse(BaseModel):
    results: list[TestCaseResultOut]


def to_question_out(question) -> QuestionOut:
    """Builds a QuestionOut from an ORM Question, redacting hidden test cases' input/expected
    output so they aren't visible before the candidate submits (they're only revealed in the
    EvaluationResponse after a real submission)."""
    out = QuestionOut.model_validate(question)
    out.test_cases = [
        tc if not tc.is_hidden else QuestionTestCaseOut(id=tc.id, input="", expected_output="", is_hidden=True)
        for tc in out.test_cases
    ]
    return out
