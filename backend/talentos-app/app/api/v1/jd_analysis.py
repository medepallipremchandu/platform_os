import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentActor, current_actor, get_db, require_permission
from app.core import permissions
from app.core.exceptions import NotFoundError
from app.core.iam_client import post_audit_event
from app.models.jd_analysis import JDAnalysis
from app.schemas.common import AuditLogEntryOut
from app.schemas.jd_analysis import (
    JDAnalysisRequest,
    JDAnalysisResponse,
    JDAnalysisSummary,
    JDAnalysisUpdateRequest,
)
from app.services.audit_service import get_audit_log
from app.services.jd_analysis_service import analyze_jd, soft_delete_jd_analysis, update_jd_analysis

router = APIRouter(prefix="/jd-analysis", tags=["jd-analysis"])


def _get_jd_or_404(db: Session, jd_analysis_id: UUID, organization_id: uuid.UUID) -> JDAnalysis:
    jd_analysis = db.get(JDAnalysis, jd_analysis_id)
    if jd_analysis is None or str(jd_analysis.organization_id) != str(organization_id):
        raise NotFoundError(f"JD analysis {jd_analysis_id} not found")
    return jd_analysis


@router.post(
    "", response_model=JDAnalysisResponse, status_code=201, dependencies=[Depends(require_permission(permissions.REQUIREMENTS_WRITE))]
)
async def create_jd_analysis(
    payload: JDAnalysisRequest,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(current_actor),
):
    jd_analysis = await analyze_jd(db, payload.jd_text, actor.email_or_name, uuid.UUID(actor.org_id))
    await post_audit_event(
        actor.token, action="jd_analysis.created", target_type="jd_analysis", target_id=str(jd_analysis.id)
    )
    return jd_analysis


@router.get(
    "", response_model=list[JDAnalysisSummary], dependencies=[Depends(require_permission(permissions.REQUIREMENTS_READ))]
)
def list_jd_analyses(
    include_deleted: bool = Query(default=False),
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(current_actor),
):
    stmt = (
        select(JDAnalysis)
        .where(JDAnalysis.organization_id == uuid.UUID(actor.org_id))
        .order_by(JDAnalysis.created_at.desc())
    )
    if not include_deleted:
        stmt = stmt.where(JDAnalysis.deleted_at.is_(None))
    return db.execute(stmt).scalars().all()


@router.get(
    "/{jd_analysis_id}",
    response_model=JDAnalysisResponse,
    dependencies=[Depends(require_permission(permissions.REQUIREMENTS_READ))],
)
def get_jd_analysis(jd_analysis_id: UUID, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)):
    return _get_jd_or_404(db, jd_analysis_id, uuid.UUID(actor.org_id))


@router.patch(
    "/{jd_analysis_id}",
    response_model=JDAnalysisResponse,
    dependencies=[Depends(require_permission(permissions.REQUIREMENTS_WRITE))],
)
async def patch_jd_analysis(
    jd_analysis_id: UUID,
    payload: JDAnalysisUpdateRequest,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(current_actor),
):
    jd_analysis = _get_jd_or_404(db, jd_analysis_id, uuid.UUID(actor.org_id))
    jd_analysis = update_jd_analysis(db, jd_analysis, payload, actor.email_or_name)
    await post_audit_event(
        actor.token, action="jd_analysis.updated", target_type="jd_analysis", target_id=str(jd_analysis.id)
    )
    return jd_analysis


@router.delete(
    "/{jd_analysis_id}",
    response_model=JDAnalysisResponse,
    dependencies=[Depends(require_permission(permissions.REQUIREMENTS_DELETE))],
)
async def delete_jd_analysis(
    jd_analysis_id: UUID, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)
):
    jd_analysis = _get_jd_or_404(db, jd_analysis_id, uuid.UUID(actor.org_id))
    jd_analysis = soft_delete_jd_analysis(db, jd_analysis, actor.email_or_name)
    await post_audit_event(
        actor.token, action="jd_analysis.deleted", target_type="jd_analysis", target_id=str(jd_analysis.id)
    )
    return jd_analysis


@router.get(
    "/{jd_analysis_id}/audit-log",
    response_model=list[AuditLogEntryOut],
    dependencies=[Depends(require_permission(permissions.REQUIREMENTS_READ))],
)
def get_jd_analysis_audit_log(
    jd_analysis_id: UUID, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)
):
    _get_jd_or_404(db, jd_analysis_id, uuid.UUID(actor.org_id))
    return get_audit_log(db, "jd_analysis", jd_analysis_id)
