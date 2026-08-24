from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db
from app.core.exceptions import NotFoundError
from app.models.interview_session import InterviewSession, Skill
from app.schemas.interview_session import (
    InterviewSessionCreateRequest,
    InterviewSessionResponse,
    InterviewSessionSummary,
)
from app.services.interview_session_service import get_or_create_interview_session

router = APIRouter(prefix="/interview-sessions", tags=["interview-sessions"])


@router.post("", response_model=InterviewSessionResponse, status_code=201)
async def create_interview_session(payload: InterviewSessionCreateRequest, db: Session = Depends(get_db)):
    session = await get_or_create_interview_session(db, payload.submission_id)
    return session


@router.get("", response_model=list[InterviewSessionSummary])
def list_interview_sessions(db: Session = Depends(get_db)):
    return db.query(InterviewSession).order_by(InterviewSession.created_at.desc()).all()


@router.get("/{interview_session_id}", response_model=InterviewSessionResponse)
def get_interview_session(interview_session_id: UUID, db: Session = Depends(get_db)):
    session = (
        db.query(InterviewSession)
        .options(selectinload(InterviewSession.skills).selectinload(Skill.rubrics))
        .filter(InterviewSession.id == interview_session_id)
        .first()
    )
    if session is None:
        raise NotFoundError(f"Interview session {interview_session_id} not found")
    return session
