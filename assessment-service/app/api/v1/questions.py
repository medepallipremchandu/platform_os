from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, get_llm_client
from app.core.exceptions import NotFoundError
from app.models.interview_session import Skill
from app.models.question import Question
from app.schemas.question import (
    QuestionGenerateBatchRequest,
    QuestionGenerateRequest,
    QuestionGenerateResponse,
    QuestionOut,
    RunCodeRequest,
    RunCodeResponse,
    to_question_out,
)
from app.schemas.evaluation import TestCaseResultOut
from app.services.llm.llm_client import LLMClient
from app.services.question_service import generate_questions, run_candidate_code_dry

router = APIRouter(prefix="/questions", tags=["questions"])


def _load_questions_for_skill(db: Session, skill_id: UUID) -> list[Question]:
    return (
        db.query(Question)
        .options(selectinload(Question.rubric_maps), selectinload(Question.test_cases))
        .filter(Question.skill_id == skill_id)
        .order_by(Question.created_at)
        .all()
    )


def _get_question_or_404(db: Session, question_id: UUID) -> Question:
    question = (
        db.query(Question)
        .options(selectinload(Question.rubric_maps), selectinload(Question.test_cases))
        .filter(Question.id == question_id)
        .first()
    )
    if question is None:
        raise NotFoundError(f"Question {question_id} not found")
    return question


@router.post("/generate", response_model=QuestionGenerateResponse, status_code=201)
async def create_questions(
    payload: QuestionGenerateRequest,
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
):
    skill = db.get(Skill, payload.skill_id)
    if skill is None:
        raise NotFoundError(f"Skill {payload.skill_id} not found")

    questions = await generate_questions(db, skill, payload.num_questions, llm_client, payload.question_type)
    return QuestionGenerateResponse(
        skill_id=skill.id, skill_name=skill.name, questions=[to_question_out(q) for q in questions]
    )


@router.post("/generate-batch", response_model=list[QuestionGenerateResponse], status_code=201)
async def create_questions_batch(
    payload: QuestionGenerateBatchRequest,
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
):
    """Lets the caller configure count + question type per skill and generate all of them
    from a single 'Generate questions' action, instead of one call per skill."""
    responses: list[QuestionGenerateResponse] = []
    for config in payload.configs:
        skill = db.get(Skill, config.skill_id)
        if skill is None:
            raise NotFoundError(f"Skill {config.skill_id} not found")
        questions = await generate_questions(db, skill, config.num_questions, llm_client, config.question_type)
        responses.append(
            QuestionGenerateResponse(
                skill_id=skill.id, skill_name=skill.name, questions=[to_question_out(q) for q in questions]
            )
        )
    return responses


@router.get("/{skill_id}", response_model=list[QuestionOut])
def list_questions_for_skill(skill_id: UUID, db: Session = Depends(get_db)):
    skill = db.get(Skill, skill_id)
    if skill is None:
        raise NotFoundError(f"Skill {skill_id} not found")
    return [to_question_out(q) for q in _load_questions_for_skill(db, skill_id)]


@router.post("/{question_id}/run-code", response_model=RunCodeResponse)
def run_code(question_id: UUID, payload: RunCodeRequest, db: Session = Depends(get_db)):
    """Executes the candidate's current code against visible test cases only - does not
    persist anything. Backs the "Run" / "Run all testcases" buttons, distinct from a real
    (persisted) submission via POST /evaluations or /evaluations/submit-batch."""
    question = _get_question_or_404(db, question_id)
    results = run_candidate_code_dry(question, payload.code, payload.scope)
    return RunCodeResponse(
        results=[
            TestCaseResultOut(
                input=r.test_case.input,
                expected_output=r.test_case.expected_output,
                actual_output=r.actual_output,
                passed=r.passed,
                is_hidden=r.test_case.is_hidden,
                stderr=r.stderr,
                execution_time_ms=r.execution_time_ms,
            )
            for r in results
        ]
    )
