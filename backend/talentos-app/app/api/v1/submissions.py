import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import CurrentActor, current_actor, get_db, require_permission
from app.core import permissions
from app.core.exceptions import NotFoundError
from app.core.iam_client import post_audit_event
from app.models.jd_analysis import JDAnalysis
from app.models.resume_analysis import ResumeAnalysis
from app.models.submission import Submission
from app.schemas.common import AuditLogEntryOut
from app.schemas.submission import SubmissionCreateRequest, SubmissionResponse, SubmissionSummary
from app.schemas.voice_call import ConversationTurnResponse, SubmissionCallResponse
from app.services import voice_agent_client, voice_call_service
from app.services.audit_service import get_audit_log
from app.services.submission_service import create_submission, soft_delete_submission

router = APIRouter(prefix="/submissions", tags=["submissions"])


def _get_submission_or_404(db: Session, submission_id: UUID, organization_id: uuid.UUID) -> Submission:
    submission = (
        db.query(Submission)
        .options(selectinload(Submission.match_analysis))
        .filter(Submission.id == submission_id)
        .first()
    )
    if submission is None or str(submission.organization_id) != str(organization_id):
        raise NotFoundError(f"Submission {submission_id} not found")
    return submission


def _get_jd_or_404(db: Session, jd_analysis_id: UUID, organization_id: uuid.UUID) -> JDAnalysis:
    jd_analysis = db.get(JDAnalysis, jd_analysis_id)
    if jd_analysis is None or str(jd_analysis.organization_id) != str(organization_id):
        raise NotFoundError(f"JD analysis {jd_analysis_id} not found")
    return jd_analysis


def _get_resume_or_404(db: Session, resume_analysis_id: UUID, organization_id: uuid.UUID) -> ResumeAnalysis:
    resume_analysis = db.get(ResumeAnalysis, resume_analysis_id)
    if resume_analysis is None or str(resume_analysis.organization_id) != str(organization_id):
        raise NotFoundError(f"Resume analysis {resume_analysis_id} not found")
    return resume_analysis


@router.post(
    "", response_model=SubmissionResponse, status_code=201, dependencies=[Depends(require_permission(permissions.SUBMISSIONS_WRITE))]
)
async def create_submission_endpoint(
    payload: SubmissionCreateRequest,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(current_actor),
):
    org_id = uuid.UUID(actor.org_id)
    jd_analysis = _get_jd_or_404(db, payload.jd_analysis_id, org_id)
    resume_analysis = _get_resume_or_404(db, payload.resume_analysis_id, org_id)

    submission = await create_submission(db, jd_analysis, resume_analysis, actor.email_or_name, org_id)
    await post_audit_event(
        actor.token, action="submission.created", target_type="submission", target_id=str(submission.id)
    )
    return _get_submission_or_404(db, submission.id, org_id)


@router.get(
    "", response_model=list[SubmissionSummary], dependencies=[Depends(require_permission(permissions.SUBMISSIONS_READ))]
)
def list_submissions(
    include_deleted: bool = Query(default=False),
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(current_actor),
):
    stmt = (
        select(Submission)
        .options(
            selectinload(Submission.match_analysis),
            selectinload(Submission.jd_analysis),
            selectinload(Submission.resume_analysis),
        )
        .where(Submission.organization_id == uuid.UUID(actor.org_id))
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


@router.get(
    "/{submission_id}",
    response_model=SubmissionResponse,
    dependencies=[Depends(require_permission(permissions.SUBMISSIONS_READ))],
)
def get_submission(submission_id: UUID, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)):
    return _get_submission_or_404(db, submission_id, uuid.UUID(actor.org_id))


@router.delete(
    "/{submission_id}",
    response_model=SubmissionResponse,
    dependencies=[Depends(require_permission(permissions.SUBMISSIONS_DELETE))],
)
async def delete_submission(
    submission_id: UUID, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)
):
    org_id = uuid.UUID(actor.org_id)
    submission = _get_submission_or_404(db, submission_id, org_id)
    soft_delete_submission(db, submission, actor.email_or_name)
    await post_audit_event(
        actor.token, action="submission.deleted", target_type="submission", target_id=str(submission_id)
    )
    return _get_submission_or_404(db, submission_id, org_id)


@router.get(
    "/{submission_id}/audit-log",
    response_model=list[AuditLogEntryOut],
    dependencies=[Depends(require_permission(permissions.SUBMISSIONS_READ))],
)
def get_submission_audit_log(
    submission_id: UUID, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)
):
    _get_submission_or_404(db, submission_id, uuid.UUID(actor.org_id))
    return get_audit_log(db, "submission", submission_id)


def _get_submission_call_or_404(db: Session, submission_id: UUID, call_id: UUID):
    from app.models.voice_call import SubmissionCall

    call = db.get(SubmissionCall, call_id)
    if call is None or call.submission_id != submission_id:
        raise NotFoundError(f"Call {call_id} not found on submission {submission_id}")
    return call


@router.post(
    "/{submission_id}/calls",
    response_model=SubmissionCallResponse,
    status_code=202,
    dependencies=[Depends(require_permission(permissions.SUBMISSIONS_WRITE))],
)
async def trigger_submission_call(
    submission_id: UUID, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)
):
    submission = _get_submission_or_404(db, submission_id, uuid.UUID(actor.org_id))
    call = await voice_call_service.trigger_submission_call(db, submission, actor.email_or_name)
    await post_audit_event(
        actor.token,
        action="submission_call.triggered",
        target_type="submission",
        target_id=str(submission_id),
        changes={"submission_call_id": {"old": None, "new": str(call.id)}},
    )
    return call


@router.get(
    "/{submission_id}/calls",
    response_model=list[SubmissionCallResponse],
    dependencies=[Depends(require_permission(permissions.SUBMISSIONS_READ))],
)
async def list_submission_calls(
    submission_id: UUID, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)
):
    _get_submission_or_404(db, submission_id, uuid.UUID(actor.org_id))
    calls = voice_call_service.list_submission_calls(db, submission_id)
    return await voice_call_service.refresh_non_terminal_calls(db, calls)


@router.get(
    "/{submission_id}/calls/{call_id}/conversation",
    response_model=list[ConversationTurnResponse],
    dependencies=[Depends(require_permission(permissions.SUBMISSIONS_READ))],
)
async def get_submission_call_conversation(
    submission_id: UUID, call_id: UUID, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)
):
    _get_submission_or_404(db, submission_id, uuid.UUID(actor.org_id))
    call = _get_submission_call_or_404(db, submission_id, call_id)
    # Live-proxied, never cached locally - always reflects voice-agent-service's own transcript.
    return await voice_agent_client.get_conversation(call.voice_agent_call_id)
