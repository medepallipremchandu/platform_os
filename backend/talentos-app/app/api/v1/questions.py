import uuid
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app.api.deps import CurrentActor, current_actor, get_db, require_permission
from app.core import permissions
from app.core.exceptions import NotFoundError
from app.core.iam_client import post_audit_event
from app.models.jd_analysis import JDAnalysis, Skill
from app.models.question import Question
from app.schemas.evaluation import TestCaseResultOut
from app.schemas.question import (
    QuestionGenerateBatchRequest,
    QuestionGenerateRequest,
    QuestionGenerateResponse,
    QuestionOut,
    RunCodeRequest,
    RunCodeResponse,
    to_question_out,
)
from app.services.question_service import generate_questions, run_candidate_code_dry

router = APIRouter(prefix="/questions", tags=["questions"])


def _get_skill_or_404(db: Session, skill_id: UUID, organization_id: uuid.UUID) -> Skill:
    skill = (
        db.query(Skill)
        .join(JDAnalysis, Skill.jd_analysis_id == JDAnalysis.id)
        .filter(Skill.id == skill_id, JDAnalysis.organization_id == organization_id)
        .first()
    )
    if skill is None:
        raise NotFoundError(f"Skill {skill_id} not found")
    return skill


def _load_questions_for_skill(db: Session, skill_id: UUID) -> list[Question]:
    return (
        db.query(Question)
        .options(selectinload(Question.rubric_maps), selectinload(Question.test_cases))
        .filter(Question.skill_id == skill_id)
        .order_by(Question.created_at)
        .all()
    )


def _get_question_or_404(db: Session, question_id: UUID, organization_id: uuid.UUID) -> Question:
    question = (
        db.query(Question)
        .join(Skill, Question.skill_id == Skill.id)
        .join(JDAnalysis, Skill.jd_analysis_id == JDAnalysis.id)
        .options(selectinload(Question.rubric_maps), selectinload(Question.test_cases))
        .filter(Question.id == question_id, JDAnalysis.organization_id == organization_id)
        .first()
    )
    if question is None:
        raise NotFoundError(f"Question {question_id} not found")
    return question


@router.post(
    "/generate",
    response_model=QuestionGenerateResponse,
    status_code=201,
    dependencies=[Depends(require_permission(permissions.INTERVIEWS_WRITE))],
)
async def create_questions(
    payload: QuestionGenerateRequest, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)
):
    skill = _get_skill_or_404(db, payload.skill_id, uuid.UUID(actor.org_id))

    questions = await generate_questions(db, skill, payload.num_questions, payload.question_type)
    await post_audit_event(
        actor.token, action="questions.generated", target_type="skill", target_id=str(skill.id)
    )
    return QuestionGenerateResponse(
        skill_id=skill.id, skill_name=skill.name, questions=[to_question_out(q) for q in questions]
    )


@router.post(
    "/generate-batch",
    response_model=list[QuestionGenerateResponse],
    status_code=201,
    dependencies=[Depends(require_permission(permissions.INTERVIEWS_WRITE))],
)
async def create_questions_batch(
    payload: QuestionGenerateBatchRequest, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)
):
    """Lets the caller configure count + question type per skill and generate all of them
    from a single 'Generate questions' action, instead of one call per skill."""
    org_id = uuid.UUID(actor.org_id)
    responses: list[QuestionGenerateResponse] = []
    for config in payload.configs:
        skill = _get_skill_or_404(db, config.skill_id, org_id)
        questions = await generate_questions(db, skill, config.num_questions, config.question_type)
        await post_audit_event(
            actor.token, action="questions.generated", target_type="skill", target_id=str(skill.id)
        )
        responses.append(
            QuestionGenerateResponse(
                skill_id=skill.id, skill_name=skill.name, questions=[to_question_out(q) for q in questions]
            )
        )
    return responses


@router.get(
    "/{skill_id}", response_model=list[QuestionOut], dependencies=[Depends(require_permission(permissions.INTERVIEWS_READ))]
)
def list_questions_for_skill(skill_id: UUID, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)):
    _get_skill_or_404(db, skill_id, uuid.UUID(actor.org_id))
    return [to_question_out(q) for q in _load_questions_for_skill(db, skill_id)]


@router.post(
    "/{question_id}/run-code",
    response_model=RunCodeResponse,
    dependencies=[Depends(require_permission(permissions.INTERVIEWS_WRITE))],
)
def run_code(
    question_id: UUID, payload: RunCodeRequest, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)
):
    """Executes the candidate's current code against visible test cases only - does not
    persist anything. Backs the "Run" / "Run all testcases" buttons, distinct from a real
    (persisted) submission via POST /evaluations or /evaluations/submit-batch."""
    question = _get_question_or_404(db, question_id, uuid.UUID(actor.org_id))
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
