import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentActor, current_actor, get_db, require_permission
from app.core import permissions
from app.core.exceptions import NotFoundError
from app.core.iam_client import post_audit_event
from app.models.jd_analysis import JDAnalysis, Rubric, Skill
from app.schemas.common import AuditLogEntryOut
from app.schemas.jd_analysis import (
    JDAnalysisRequest,
    JDAnalysisResponse,
    JDAnalysisSummary,
    JDAnalysisUpdateRequest,
    RubricOut,
    RubricUpdateRequest,
    SkillOut,
    SkillUpdateRequest,
)
from app.schemas.voice_call import JDCallAgentConfigRequest, JDCallAgentConfigResponse
from app.services import voice_call_service
from app.services.audit_service import get_audit_log
from app.services.jd_analysis_service import (
    analyze_jd,
    soft_delete_jd_analysis,
    update_jd_analysis,
    update_rubric,
    update_skill,
)

router = APIRouter(prefix="/jd-analysis", tags=["jd-analysis"])


def _get_jd_or_404(db: Session, jd_analysis_id: UUID, organization_id: uuid.UUID) -> JDAnalysis:
    jd_analysis = db.get(JDAnalysis, jd_analysis_id)
    if jd_analysis is None or str(jd_analysis.organization_id) != str(organization_id):
        raise NotFoundError(f"JD analysis {jd_analysis_id} not found")
    return jd_analysis


def _get_skill_or_404(jd_analysis: JDAnalysis, skill_id: UUID) -> Skill:
    for skill in jd_analysis.skills:
        if skill.id == skill_id:
            return skill
    raise NotFoundError(f"Skill {skill_id} not found on JD analysis {jd_analysis.id}")


def _get_rubric_or_404(jd_analysis: JDAnalysis, rubric_id: UUID) -> tuple[Skill, Rubric]:
    """Rubrics are addressed directly by id under the JD (not nested under a skill segment in
    the URL), so this walks every skill's rubrics to find the owning skill + rubric pair."""
    for skill in jd_analysis.skills:
        for rubric in skill.rubrics:
            if rubric.id == rubric_id:
                return skill, rubric
    raise NotFoundError(f"Rubric {rubric_id} not found on JD analysis {jd_analysis.id}")


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


@router.patch(
    "/{jd_analysis_id}/skills/{skill_id}",
    response_model=SkillOut,
    dependencies=[Depends(require_permission(permissions.REQUIREMENTS_WRITE))],
)
async def patch_skill(
    jd_analysis_id: UUID,
    skill_id: UUID,
    payload: SkillUpdateRequest,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(current_actor),
):
    jd_analysis = _get_jd_or_404(db, jd_analysis_id, uuid.UUID(actor.org_id))
    skill = _get_skill_or_404(jd_analysis, skill_id)
    skill = update_skill(db, jd_analysis, skill, payload, actor.email_or_name)
    await post_audit_event(
        actor.token, action="jd_analysis.skill_updated", target_type="jd_analysis", target_id=str(jd_analysis.id)
    )
    return skill


@router.patch(
    "/{jd_analysis_id}/rubrics/{rubric_id}",
    response_model=RubricOut,
    dependencies=[Depends(require_permission(permissions.REQUIREMENTS_WRITE))],
)
async def patch_rubric(
    jd_analysis_id: UUID,
    rubric_id: UUID,
    payload: RubricUpdateRequest,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(current_actor),
):
    jd_analysis = _get_jd_or_404(db, jd_analysis_id, uuid.UUID(actor.org_id))
    skill, rubric = _get_rubric_or_404(jd_analysis, rubric_id)
    rubric = update_rubric(db, jd_analysis, skill, rubric, payload, actor.email_or_name)
    await post_audit_event(
        actor.token, action="jd_analysis.rubric_updated", target_type="jd_analysis", target_id=str(jd_analysis.id)
    )
    return rubric


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


@router.get(
    "/{jd_analysis_id}/call-config",
    response_model=JDCallAgentConfigResponse | None,
    dependencies=[Depends(require_permission(permissions.REQUIREMENTS_READ))],
)
def get_jd_call_config(
    jd_analysis_id: UUID, db: Session = Depends(get_db), actor: CurrentActor = Depends(current_actor)
):
    _get_jd_or_404(db, jd_analysis_id, uuid.UUID(actor.org_id))
    return voice_call_service.get_jd_call_config(db, jd_analysis_id)


@router.put(
    "/{jd_analysis_id}/call-config",
    response_model=JDCallAgentConfigResponse,
    dependencies=[Depends(require_permission(permissions.REQUIREMENTS_WRITE))],
)
async def put_jd_call_config(
    jd_analysis_id: UUID,
    payload: JDCallAgentConfigRequest,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(current_actor),
):
    jd_analysis = _get_jd_or_404(db, jd_analysis_id, uuid.UUID(actor.org_id))
    config = voice_call_service.upsert_jd_call_config(db, jd_analysis, payload, actor.email_or_name)
    await post_audit_event(
        actor.token, action="jd_call_config.updated", target_type="jd_analysis", target_id=str(jd_analysis_id)
    )
    return config
