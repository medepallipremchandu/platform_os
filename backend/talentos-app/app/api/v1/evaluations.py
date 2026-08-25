import uuid
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app.api.deps import CurrentActor, current_actor, get_db, require_permission
from app.core import permissions
from app.core.exceptions import NotFoundError
from app.core.iam_client import post_audit_event
from app.models.evaluation import Evaluation
from app.models.jd_analysis import JDAnalysis, Skill
from app.models.question import Question
from app.schemas.evaluation import BatchEvaluationResponse, EvaluationRequest, EvaluationResponse, SubmitBatchRequest
from app.services.evaluation_service import evaluate_answer, evaluate_batch

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


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


def _get_evaluation_or_404(db: Session, evaluation_id: UUID, organization_id: uuid.UUID) -> Evaluation:
    evaluation = (
        db.query(Evaluation)
        .join(Question, Evaluation.question_id == Question.id)
        .join(Skill, Question.skill_id == Skill.id)
        .join(JDAnalysis, Skill.jd_analysis_id == JDAnalysis.id)
        .filter(Evaluation.id == evaluation_id, JDAnalysis.organization_id == organization_id)
        .first()
    )
    if evaluation is None:
        raise NotFoundError(f"Evaluation {evaluation_id} not found")
    return evaluation


@router.post(
    "", response_model=EvaluationResponse, status_code=201, dependencies=[Depends(require_permission(permissions.INTERVIEWS_WRITE))]
)
async def create_evaluation(
    payload: EvaluationRequest, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)
):
    question = _get_question_or_404(db, payload.question_id, uuid.UUID(actor.org_id))

    evaluation = await evaluate_answer(db, question, payload)
    await post_audit_event(
        actor.token, action="evaluation.created", target_type="evaluation", target_id=str(evaluation.id)
    )
    return evaluation


@router.post(
    "/submit-batch",
    response_model=BatchEvaluationResponse,
    status_code=201,
    dependencies=[Depends(require_permission(permissions.INTERVIEWS_WRITE))],
)
async def submit_batch_evaluation(
    payload: SubmitBatchRequest, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)
):
    """The 'Final Submit' action - evaluates every answered question in one call and returns
    the candidate's overall score card (total + per-skill breakdown)."""
    org_id = uuid.UUID(actor.org_id)
    for answer in payload.answers:
        _get_question_or_404(db, answer.question_id, org_id)

    evaluations, overall, skill_scores = await evaluate_batch(db, payload.answers)
    await post_audit_event(
        actor.token, action="evaluation.submitted_batch", target_type="evaluation", target_id=None
    )
    return BatchEvaluationResponse(overall_score_percentage=overall, evaluations=evaluations, skill_scores=skill_scores)


@router.get(
    "/{evaluation_id}",
    response_model=EvaluationResponse,
    dependencies=[Depends(require_permission(permissions.INTERVIEWS_READ))],
)
def get_evaluation(evaluation_id: UUID, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)):
    return _get_evaluation_or_404(db, evaluation_id, uuid.UUID(actor.org_id))
