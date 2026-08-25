import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.jd_analysis import JDAnalysis, Rubric, Skill
from app.schemas.jd_analysis import JDAnalysisUpdateRequest
from app.schemas.llm_outputs import LLMJDExtraction, LLMSkill
from app.services import agent_client
from app.services.audit_service import record_audit

logger = logging.getLogger("app.services.jd_analysis")

_UPDATABLE_FIELDS = ("job_title", "role_context", "job_context_summary", "responsibilities", "qualifications")


def _normalize_rubric_weights(skill: LLMSkill) -> LLMSkill:
    """Rescale a skill's rubric weights so they sum to exactly 100, in case the agent is slightly off."""
    total = sum(r.weight_percentage for r in skill.rubrics)
    if total <= 0:
        return skill
    if abs(total - 100) < 0.5:
        return skill
    for rubric in skill.rubrics:
        rubric.weight_percentage = round(rubric.weight_percentage * 100 / total, 2)
    return skill


def _next_jd_code(db: Session) -> str:
    seq_value = db.execute(text("SELECT nextval('jd_code_seq')")).scalar_one()
    return f"TOS{seq_value:02d}"


async def analyze_jd(db: Session, jd_text: str, actor: str, organization_id: uuid.UUID) -> JDAnalysis:
    raw_output = await agent_client.invoke("JD_ANALYSIS_AGENT", {"jd_text": jd_text})
    extraction = LLMJDExtraction.model_validate(raw_output)

    jd_analysis = JDAnalysis(
        organization_id=organization_id,
        jd_code=_next_jd_code(db),
        jd_text=jd_text,
        job_title=extraction.job_title,
        role_context=extraction.role_context,
        job_context_summary=extraction.job_context_summary,
        responsibilities=extraction.responsibilities,
        qualifications=extraction.qualifications,
        raw_llm_response=extraction.model_dump(),
        created_by=actor,
    )

    for llm_skill in extraction.skills:
        llm_skill = _normalize_rubric_weights(llm_skill)
        skill = Skill(name=llm_skill.name, description=llm_skill.description)
        for llm_rubric in llm_skill.rubrics:
            skill.rubrics.append(
                Rubric(
                    name=llm_rubric.name,
                    description=llm_rubric.description,
                    weight_percentage=llm_rubric.weight_percentage,
                )
            )
        jd_analysis.skills.append(skill)

    db.add(jd_analysis)
    db.flush()  # assign jd_analysis.id before the audit log needs it
    record_audit(db, "jd_analysis", jd_analysis.id, "created", actor)
    db.commit()
    db.refresh(jd_analysis)
    logger.info(
        "JD analysis %s (%s) created with %d skills", jd_analysis.jd_code, jd_analysis.id, len(jd_analysis.skills)
    )
    return jd_analysis


def update_jd_analysis(
    db: Session, jd_analysis: JDAnalysis, payload: JDAnalysisUpdateRequest, actor: str
) -> JDAnalysis:
    changes: dict[str, dict] = {}
    for field in _UPDATABLE_FIELDS:
        new_value = getattr(payload, field)
        if new_value is None:
            continue
        old_value = getattr(jd_analysis, field)
        if old_value != new_value:
            changes[field] = {"old": old_value, "new": new_value}
            setattr(jd_analysis, field, new_value)

    if changes:
        jd_analysis.modified_by = actor
        jd_analysis.modified_at = datetime.now(timezone.utc)
        record_audit(db, "jd_analysis", jd_analysis.id, "updated", actor, changes)
        db.commit()
        db.refresh(jd_analysis)
        logger.info("JD analysis %s updated by %s: %s", jd_analysis.jd_code, actor, list(changes.keys()))
    return jd_analysis


def soft_delete_jd_analysis(db: Session, jd_analysis: JDAnalysis, actor: str) -> JDAnalysis:
    jd_analysis.deleted_by = actor
    jd_analysis.deleted_at = datetime.now(timezone.utc)
    record_audit(db, "jd_analysis", jd_analysis.id, "deleted", actor)
    db.commit()
    db.refresh(jd_analysis)
    logger.info("JD analysis %s soft-deleted by %s", jd_analysis.jd_code, actor)
    return jd_analysis
