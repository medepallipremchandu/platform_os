from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_actor, get_db, get_llm_client
from app.core.exceptions import NotFoundError
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
from app.services.llm.llm_client import LLMClient

router = APIRouter(prefix="/jd-analysis", tags=["jd-analysis"])


def _get_jd_or_404(db: Session, jd_analysis_id: UUID) -> JDAnalysis:
    jd_analysis = db.get(JDAnalysis, jd_analysis_id)
    if jd_analysis is None:
        raise NotFoundError(f"JD analysis {jd_analysis_id} not found")
    return jd_analysis


@router.post("", response_model=JDAnalysisResponse, status_code=201)
async def create_jd_analysis(
    payload: JDAnalysisRequest,
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
    actor: str = Depends(get_actor),
):
    jd_analysis = await analyze_jd(db, payload.jd_text, llm_client, actor)
    return jd_analysis


@router.get("", response_model=list[JDAnalysisSummary])
def list_jd_analyses(include_deleted: bool = Query(default=False), db: Session = Depends(get_db)):
    stmt = select(JDAnalysis).order_by(JDAnalysis.created_at.desc())
    if not include_deleted:
        stmt = stmt.where(JDAnalysis.deleted_at.is_(None))
    return db.execute(stmt).scalars().all()


@router.get("/{jd_analysis_id}", response_model=JDAnalysisResponse)
def get_jd_analysis(jd_analysis_id: UUID, db: Session = Depends(get_db)):
    return _get_jd_or_404(db, jd_analysis_id)


@router.patch("/{jd_analysis_id}", response_model=JDAnalysisResponse)
def patch_jd_analysis(
    jd_analysis_id: UUID,
    payload: JDAnalysisUpdateRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(get_actor),
):
    jd_analysis = _get_jd_or_404(db, jd_analysis_id)
    return update_jd_analysis(db, jd_analysis, payload, actor)


@router.delete("/{jd_analysis_id}", response_model=JDAnalysisResponse)
def delete_jd_analysis(jd_analysis_id: UUID, db: Session = Depends(get_db), actor: str = Depends(get_actor)):
    jd_analysis = _get_jd_or_404(db, jd_analysis_id)
    return soft_delete_jd_analysis(db, jd_analysis, actor)


@router.get("/{jd_analysis_id}/audit-log", response_model=list[AuditLogEntryOut])
def get_jd_analysis_audit_log(jd_analysis_id: UUID, db: Session = Depends(get_db)):
    _get_jd_or_404(db, jd_analysis_id)
    return get_audit_log(db, "jd_analysis", jd_analysis_id)
