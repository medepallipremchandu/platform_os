import logging
import uuid

from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import NotFoundError
from app.models.interview_session import InterviewSession
from app.models.jd_analysis import JDAnalysis
from app.models.submission import Submission

logger = logging.getLogger("app.services.interview_session")


def get_or_create_interview_session(db: Session, submission_id: uuid.UUID, actor: str) -> InterviewSession:
    """Idempotent: if this submission already has an interview session, return it unchanged."""
    existing = db.query(InterviewSession).filter(InterviewSession.submission_id == submission_id).first()
    if existing is not None:
        return existing

    submission = (
        db.query(Submission)
        .options(selectinload(Submission.jd_analysis).selectinload(JDAnalysis.skills))
        .filter(Submission.id == submission_id)
        .first()
    )
    if submission is None:
        raise NotFoundError(f"Submission {submission_id} not found")

    session = InterviewSession(submission_id=submission_id, created_by=actor)
    db.add(session)
    db.commit()
    db.refresh(session)
    logger.info("Interview session %s created for submission %s", session.id, submission.submission_code)
    return session
