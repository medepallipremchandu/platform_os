"""Schemas the LLM's JSON output is validated against. Not exposed via the API directly."""
from pydantic import BaseModel, Field


class LLMQuestionRubricMap(BaseModel):
    rubric_name: str
    weight_percentage: float = Field(ge=0, le=100)
    evaluation_criteria: str


class LLMTestCase(BaseModel):
    input: str
    expected_output: str
    is_hidden: bool = False


class LLMQuestion(BaseModel):
    question_text: str
    difficulty: str
    rubric_maps: list[LLMQuestionRubricMap]

    # mcq only
    options: list[str] | None = None
    correct_option_index: int | None = None

    # coding only
    language: str | None = None
    starter_code: str | None = None
    test_cases: list[LLMTestCase] | None = None


class LLMQuestionGeneration(BaseModel):
    questions: list[LLMQuestion]


class LLMRubricScore(BaseModel):
    rubric_name: str
    achieved_score_percentage: float = Field(ge=0, le=100)
    feedback: str


class LLMEvaluation(BaseModel):
    rubric_scores: list[LLMRubricScore]
    summary: str
