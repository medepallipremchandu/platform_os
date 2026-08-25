import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentActor, current_actor, get_db, require_permission
from app.config import get_settings
from app.core import permissions
from app.core.exceptions import InvalidStateError, NotFoundError
from app.core.iam_client import post_audit_event
from app.models.resume_analysis import ResumeAnalysis
from app.schemas.common import AuditLogEntryOut
from app.schemas.resume_analysis import ResumeAnalysisResponse, ResumeAnalysisSummary
from app.services.audit_service import get_audit_log
from app.services.resume_analysis_service import analyze_resume, soft_delete_resume_analysis

router = APIRouter(prefix="/resume-analysis", tags=["resume-analysis"])


def _get_resume_or_404(db: Session, resume_analysis_id: UUID, organization_id: uuid.UUID) -> ResumeAnalysis:
    resume_analysis = db.get(ResumeAnalysis, resume_analysis_id)
    if resume_analysis is None or str(resume_analysis.organization_id) != str(organization_id):
        raise NotFoundError(f"Resume analysis {resume_analysis_id} not found")
    return resume_analysis


@router.post(
    "",
    response_model=ResumeAnalysisResponse,
    status_code=201,
    dependencies=[Depends(require_permission(permissions.APPLICANTS_WRITE))],
)
async def create_resume_analysis(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(current_actor),
):
    settings = get_settings()
    file_bytes = await file.read()
    if len(file_bytes) > settings.MAX_RESUME_FILE_SIZE_BYTES:
        raise InvalidStateError(
            f"File too large ({len(file_bytes)} bytes) - max {settings.MAX_RESUME_FILE_SIZE_BYTES} bytes"
        )
    resume_analysis = await analyze_resume(
        db, file.filename or "resume", file_bytes, actor.email_or_name, uuid.UUID(actor.org_id)
    )
    await post_audit_event(
        actor.token, action="resume_analysis.created", target_type="resume_analysis", target_id=str(resume_analysis.id)
    )
    return resume_analysis


@router.get(
    "", response_model=list[ResumeAnalysisSummary], dependencies=[Depends(require_permission(permissions.APPLICANTS_READ))]
)
def list_resume_analyses(
    include_deleted: bool = Query(default=False),
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(current_actor),
):
    stmt = (
        select(ResumeAnalysis)
        .where(ResumeAnalysis.organization_id == uuid.UUID(actor.org_id))
        .order_by(ResumeAnalysis.created_at.desc())
    )
    if not include_deleted:
        stmt = stmt.where(ResumeAnalysis.deleted_at.is_(None))
    return db.execute(stmt).scalars().all()


@router.get(
    "/{resume_analysis_id}",
    response_model=ResumeAnalysisResponse,
    dependencies=[Depends(require_permission(permissions.APPLICANTS_READ))],
)
def get_resume_analysis(
    resume_analysis_id: UUID, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)
):
    return _get_resume_or_404(db, resume_analysis_id, uuid.UUID(actor.org_id))


@router.delete(
    "/{resume_analysis_id}",
    response_model=ResumeAnalysisResponse,
    dependencies=[Depends(require_permission(permissions.APPLICANTS_DELETE))],
)
async def delete_resume_analysis(
    resume_analysis_id: UUID, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)
):
    resume_analysis = _get_resume_or_404(db, resume_analysis_id, uuid.UUID(actor.org_id))
    resume_analysis = soft_delete_resume_analysis(db, resume_analysis, actor.email_or_name)
    await post_audit_event(
        actor.token, action="resume_analysis.deleted", target_type="resume_analysis", target_id=str(resume_analysis.id)
    )
    return resume_analysis


@router.get(
    "/{resume_analysis_id}/audit-log",
    response_model=list[AuditLogEntryOut],
    dependencies=[Depends(require_permission(permissions.APPLICANTS_READ))],
)
def get_resume_analysis_audit_log(
    resume_analysis_id: UUID, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)
):
    _get_resume_or_404(db, resume_analysis_id, uuid.UUID(actor.org_id))
    return get_audit_log(db, "resume_analysis", resume_analysis_id)
