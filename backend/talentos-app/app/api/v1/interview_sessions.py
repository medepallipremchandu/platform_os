import uuid
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app.api.deps import CurrentActor, current_actor, get_db, require_permission
from app.core import permissions
from app.core.exceptions import NotFoundError
from app.core.iam_client import post_audit_event
from app.models.interview_session import InterviewSession
from app.models.jd_analysis import JDAnalysis
from app.models.submission import Submission
from app.schemas.interview_session import (
    InterviewSessionCreateRequest,
    InterviewSessionResponse,
    InterviewSessionSummary,
)
from app.schemas.jd_analysis import SkillOut
from app.services.interview_session_service import get_or_create_interview_session

router = APIRouter(prefix="/interview-sessions", tags=["interview-sessions"])


def _load_session_with_context(db: Session, interview_session_id: UUID, organization_id: uuid.UUID) -> InterviewSession:
    session = (
        db.query(InterviewSession)
        .join(Submission, InterviewSession.submission_id == Submission.id)
        .options(
            selectinload(InterviewSession.submission).selectinload(Submission.jd_analysis).selectinload(
                JDAnalysis.skills
            ),
            selectinload(InterviewSession.submission).selectinload(Submission.resume_analysis),
        )
        .filter(InterviewSession.id == interview_session_id, Submission.organization_id == organization_id)
        .first()
    )
    if session is None:
        raise NotFoundError(f"Interview session {interview_session_id} not found")
    return session


def _to_response(session: InterviewSession) -> InterviewSessionResponse:
    submission = session.submission
    return InterviewSessionResponse(
        id=session.id,
        submission_id=submission.id,
        submission_code=submission.submission_code,
        jd_code=submission.jd_analysis.jd_code,
        job_title=submission.jd_analysis.job_title,
        resume_code=submission.resume_analysis.resume_code,
        candidate_name=submission.resume_analysis.candidate_name,
        skills=[SkillOut.model_validate(s) for s in submission.jd_analysis.skills],
        created_by=session.created_by,
        created_at=session.created_at,
    )


@router.post(
    "",
    response_model=InterviewSessionResponse,
    status_code=201,
    dependencies=[Depends(require_permission(permissions.INTERVIEWS_WRITE))],
)
async def create_interview_session(
    payload: InterviewSessionCreateRequest, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)
):
    org_id = uuid.UUID(actor.org_id)
    submission = db.get(Submission, payload.submission_id)
    if submission is None or str(submission.organization_id) != str(org_id):
        raise NotFoundError(f"Submission {payload.submission_id} not found")

    session = get_or_create_interview_session(db, payload.submission_id, actor.email_or_name)
    await post_audit_event(
        actor.token, action="interview_session.created", target_type="interview_session", target_id=str(session.id)
    )
    return _to_response(_load_session_with_context(db, session.id, org_id))


@router.get(
    "", response_model=list[InterviewSessionSummary], dependencies=[Depends(require_permission(permissions.INTERVIEWS_READ))]
)
def list_interview_sessions(db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)):
    sessions = (
        db.query(InterviewSession)
        .join(Submission, InterviewSession.submission_id == Submission.id)
        .options(
            selectinload(InterviewSession.submission).selectinload(Submission.jd_analysis),
            selectinload(InterviewSession.submission).selectinload(Submission.resume_analysis),
        )
        .filter(Submission.organization_id == uuid.UUID(actor.org_id))
        .order_by(InterviewSession.created_at.desc())
        .all()
    )
    return [
        InterviewSessionSummary(
            id=s.id,
            submission_id=s.submission_id,
            submission_code=s.submission.submission_code,
            jd_code=s.submission.jd_analysis.jd_code,
            job_title=s.submission.jd_analysis.job_title,
            resume_code=s.submission.resume_analysis.resume_code,
            candidate_name=s.submission.resume_analysis.candidate_name,
            created_at=s.created_at,
        )
        for s in sessions
    ]


@router.get(
    "/{interview_session_id}",
    response_model=InterviewSessionResponse,
    dependencies=[Depends(require_permission(permissions.INTERVIEWS_READ))],
)
def get_interview_session(
    interview_session_id: UUID, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)
):
    return _to_response(_load_session_with_context(db, interview_session_id, uuid.UUID(actor.org_id)))
