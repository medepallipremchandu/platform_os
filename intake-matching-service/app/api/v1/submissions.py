from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_actor, get_db, get_llm_client
from app.core.exceptions import NotFoundError
from app.models.jd_analysis import JDAnalysis
from app.models.resume_analysis import ResumeAnalysis
from app.models.submission import Submission
from app.schemas.common import AuditLogEntryOut
from app.schemas.jd_analysis import SkillOut
from app.schemas.submission import (
    SubmissionCreateRequest,
    SubmissionForAssessment,
    SubmissionResponse,
    SubmissionSummary,
)
from app.services.audit_service import get_audit_log
from app.services.llm.llm_client import LLMClient
from app.services.submission_service import create_submission, soft_delete_submission

router = APIRouter(prefix="/submissions", tags=["submissions"])


def _get_submission_or_404(db: Session, submission_id: UUID) -> Submission:
    submission = (
        db.query(Submission)
        .options(selectinload(Submission.match_analysis))
        .filter(Submission.id == submission_id)
        .first()
    )
    if submission is None:
        raise NotFoundError(f"Submission {submission_id} not found")
    return submission


@router.post("", response_model=SubmissionResponse, status_code=201)
async def create_submission_endpoint(
    payload: SubmissionCreateRequest,
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
    actor: str = Depends(get_actor),
):
    jd_analysis = db.get(JDAnalysis, payload.jd_analysis_id)
    if jd_analysis is None:
        raise NotFoundError(f"JD analysis {payload.jd_analysis_id} not found")
    resume_analysis = db.get(ResumeAnalysis, payload.resume_analysis_id)
    if resume_analysis is None:
        raise NotFoundError(f"Resume analysis {payload.resume_analysis_id} not found")

    submission = await create_submission(db, jd_analysis, resume_analysis, llm_client, actor)
    return _get_submission_or_404(db, submission.id)


@router.get("", response_model=list[SubmissionSummary])
def list_submissions(include_deleted: bool = Query(default=False), db: Session = Depends(get_db)):
    stmt = (
        select(Submission)
        .options(
            selectinload(Submission.match_analysis),
            selectinload(Submission.jd_analysis),
            selectinload(Submission.resume_analysis),
        )
        .order_by(Submission.created_at.desc())
    )
    if not include_deleted:
        stmt = stmt.where(Submission.deleted_at.is_(None))
    submissions = db.execute(stmt).scalars().all()
    return [
        SubmissionSummary(
            id=s.id,
            submission_code=s.submission_code,
            jd_code=s.jd_analysis.jd_code,
            job_title=s.jd_analysis.job_title,
            resume_code=s.resume_analysis.resume_code,
            candidate_name=s.resume_analysis.candidate_name,
            overall_match_percentage=(
                float(s.match_analysis.overall_match_percentage) if s.match_analysis else None
            ),
            created_by=s.created_by,
            created_at=s.created_at,
            is_deleted=s.is_deleted,
        )
        for s in submissions
    ]


@router.get("/{submission_id}", response_model=SubmissionResponse)
def get_submission(submission_id: UUID, db: Session = Depends(get_db)):
    return _get_submission_or_404(db, submission_id)


@router.delete("/{submission_id}", response_model=SubmissionResponse)
def delete_submission(submission_id: UUID, db: Session = Depends(get_db), actor: str = Depends(get_actor)):
    submission = _get_submission_or_404(db, submission_id)
    soft_delete_submission(db, submission, actor)
    return _get_submission_or_404(db, submission_id)


@router.get("/{submission_id}/audit-log", response_model=list[AuditLogEntryOut])
def get_submission_audit_log(submission_id: UUID, db: Session = Depends(get_db)):
    _get_submission_or_404(db, submission_id)
    return get_audit_log(db, "submission", submission_id)


@router.get("/{submission_id}/for-assessment", response_model=SubmissionForAssessment)
def get_submission_for_assessment(submission_id: UUID, db: Session = Depends(get_db)):
    """Internal, service-to-service endpoint: assessment-service calls this to snapshot the
    skills/rubrics it needs to run an interview for this submission."""
    submission = (
        db.query(Submission)
        .options(
            selectinload(Submission.jd_analysis).selectinload(JDAnalysis.skills),
            selectinload(Submission.resume_analysis),
        )
        .filter(Submission.id == submission_id)
        .first()
    )
    if submission is None:
        raise NotFoundError(f"Submission {submission_id} not found")

    return SubmissionForAssessment(
        submission_id=submission.id,
        submission_code=submission.submission_code,
        jd_code=submission.jd_analysis.jd_code,
        job_title=submission.jd_analysis.job_title,
        resume_code=submission.resume_analysis.resume_code,
        candidate_name=submission.resume_analysis.candidate_name,
        skills=[SkillOut.model_validate(s) for s in submission.jd_analysis.skills],
    )
