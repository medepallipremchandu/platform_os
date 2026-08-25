import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import InvalidStateError
from app.models.jd_analysis import JDAnalysis, Rubric, Skill
from app.schemas.jd_analysis import JDAnalysisUpdateRequest, RubricUpdateRequest, SkillUpdateRequest
from app.schemas.llm_outputs import LLMJDExtraction, LLMSkill
from app.services import agent_client
from app.services.audit_service import record_audit

logger = logging.getLogger("app.services.jd_analysis")

_UPDATABLE_FIELDS = ("job_title", "role_context", "job_context_summary", "responsibilities", "qualifications")
_SKILL_UPDATABLE_FIELDS = ("name", "description")
_RUBRIC_UPDATABLE_FIELDS = ("description", "weight_percentage")

# Same tolerance _normalize_rubric_weights() uses at generation time.
_RUBRIC_WEIGHT_SUM_TOLERANCE = 0.5


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


def update_skill(db: Session, jd_analysis: JDAnalysis, skill: Skill, payload: SkillUpdateRequest, actor: str) -> Skill:
    """Skill/Rubric have no modified_by/modified_at of their own (see app/models/jd_analysis.py)
    - edits stamp the parent JDAnalysis instead, same as the rest of this file."""
    changes: dict[str, dict] = {}
    for field in _SKILL_UPDATABLE_FIELDS:
        new_value = getattr(payload, field)
        if new_value is None:
            continue
        old_value = getattr(skill, field)
        if old_value != new_value:
            changes[field] = {"old": old_value, "new": new_value}
            setattr(skill, field, new_value)

    if changes:
        jd_analysis.modified_by = actor
        jd_analysis.modified_at = datetime.now(timezone.utc)
        record_audit(db, "jd_analysis", jd_analysis.id, "skill_updated", actor, {"skill_id": str(skill.id), **changes})
        db.commit()
        db.refresh(skill)
        logger.info("Skill %s (JD %s) updated by %s: %s", skill.id, jd_analysis.jd_code, actor, list(changes.keys()))
    return skill


def update_rubric(
    db: Session, jd_analysis: JDAnalysis, skill: Skill, rubric: Rubric, payload: RubricUpdateRequest, actor: str
) -> Rubric:
    """Same modified_by/modified_at-on-parent pattern as update_skill(). weight_percentage edits
    are also checked against the same "rubric weights sum to ~100 per skill" invariant enforced
    (by rescaling) at generation time in _normalize_rubric_weights() - here it's enforced by
    rejecting the edit outright rather than silently rescaling every sibling rubric out from
    under the caller."""
    changes: dict[str, dict] = {}
    for field in _RUBRIC_UPDATABLE_FIELDS:
        new_value = getattr(payload, field)
        if new_value is None:
            continue
        old_value = getattr(rubric, field)
        if field == "weight_percentage":
            old_value = float(old_value)
        if old_value != new_value:
            changes[field] = {"old": old_value, "new": new_value}

    if "weight_percentage" in changes:
        new_weight = changes["weight_percentage"]["new"]
        sibling_total = sum(float(r.weight_percentage) for r in skill.rubrics if r.id != rubric.id)
        new_total = sibling_total + new_weight
        if abs(new_total - 100) > _RUBRIC_WEIGHT_SUM_TOLERANCE:
            raise InvalidStateError(
                f"Rubric weights for skill '{skill.name}' must sum to ~100 "
                f"(tolerance +/-{_RUBRIC_WEIGHT_SUM_TOLERANCE}). Setting this rubric's weight to "
                f"{new_weight} would make the skill's total {new_total:.2f}."
            )

    if changes:
        for field, diff in changes.items():
            setattr(rubric, field, diff["new"])
        jd_analysis.modified_by = actor
        jd_analysis.modified_at = datetime.now(timezone.utc)
        record_audit(db, "jd_analysis", jd_analysis.id, "rubric_updated", actor, {"rubric_id": str(rubric.id), **changes})
        db.commit()
        db.refresh(rubric)
        logger.info("Rubric %s (JD %s) updated by %s: %s", rubric.id, jd_analysis.jd_code, actor, list(changes.keys()))
    return rubric


def soft_delete_jd_analysis(db: Session, jd_analysis: JDAnalysis, actor: str) -> JDAnalysis:
    jd_analysis.deleted_by = actor
    jd_analysis.deleted_at = datetime.now(timezone.utc)
    record_audit(db, "jd_analysis", jd_analysis.id, "deleted", actor)
    db.commit()
    db.refresh(jd_analysis)
    logger.info("JD analysis %s soft-deleted by %s", jd_analysis.jd_code, actor)
    return jd_analysis
