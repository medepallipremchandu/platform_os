from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, get_llm_client
from app.core.exceptions import NotFoundError
from app.models.evaluation import Evaluation
from app.models.question import Question
from app.schemas.evaluation import BatchEvaluationResponse, EvaluationRequest, EvaluationResponse, SubmitBatchRequest
from app.services.evaluation_service import evaluate_answer, evaluate_batch
from app.services.llm.llm_client import LLMClient

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.post("", response_model=EvaluationResponse, status_code=201)
async def create_evaluation(
    payload: EvaluationRequest,
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
):
    question = (
        db.query(Question)
        .options(selectinload(Question.rubric_maps), selectinload(Question.test_cases))
        .filter(Question.id == payload.question_id)
        .first()
    )
    if question is None:
        raise NotFoundError(f"Question {payload.question_id} not found")

    evaluation = await evaluate_answer(db, question, payload, llm_client)
    return evaluation


@router.post("/submit-batch", response_model=BatchEvaluationResponse, status_code=201)
async def submit_batch_evaluation(
    payload: SubmitBatchRequest,
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
):
    """The 'Final Submit' action - evaluates every answered question in one call and returns
    the candidate's overall score card (total + per-skill breakdown)."""
    evaluations, overall, skill_scores = await evaluate_batch(db, payload.answers, llm_client)
    return BatchEvaluationResponse(overall_score_percentage=overall, evaluations=evaluations, skill_scores=skill_scores)


@router.get("/{evaluation_id}", response_model=EvaluationResponse)
def get_evaluation(evaluation_id: UUID, db: Session = Depends(get_db)):
    evaluation = db.get(Evaluation, evaluation_id)
    if evaluation is None:
        raise NotFoundError(f"Evaluation {evaluation_id} not found")
    return evaluation
