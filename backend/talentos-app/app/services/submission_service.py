import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.jd_analysis import JDAnalysis
from app.models.resume_analysis import ResumeAnalysis
from app.models.submission import MatchAnalysis, Submission
from app.schemas.llm_outputs import LLMMatchAnalysis
from app.services import agent_client
from app.services.audit_service import record_audit

logger = logging.getLogger("app.services.submission")


def _next_submission_code(db: Session) -> str:
    seq_value = db.execute(text("SELECT nextval('submission_code_seq')")).scalar_one()
    return f"SUB{seq_value:02d}"


def _normalize_skill_match_weights(match: LLMMatchAnalysis) -> LLMMatchAnalysis:
    total = sum(m.jd_weight_percentage for m in match.skill_matches)
    if total <= 0 or abs(total - 100) < 0.5:
        return match
    for m in match.skill_matches:
        m.jd_weight_percentage = round(m.jd_weight_percentage * 100 / total, 2)
    return match


def _build_matching_variables(jd_analysis: JDAnalysis, resume_analysis: ResumeAnalysis) -> dict[str, str]:
    """Flattens the JD/resume records into the plain string variables the Matching Agent's
    prompt template expects - the agent template only does {{name}} substitution, so any
    list-to-text formatting has to happen here, not in the template."""
    skills_block = "\n".join(
        f'- "{s.name}": {s.description or ""} (rubrics: '
        + ", ".join(f"{r.name} [{r.weight_percentage}%]" for r in s.rubrics)
        + ")"
        for s in jd_analysis.skills
    )
    resume_skills = (
        ", ".join(
            f'{s["name"]}'
            + (f' ({s["years_experience"]}y)' if s.get("years_experience") else "")
            + (f' [{s["proficiency"]}]' if s.get("proficiency") else "")
            for s in resume_analysis.skills
        )
        or "none listed"
    )
    work_history = (
        "; ".join(
            f'{w["title"]} at {w["company"]} ({w.get("start_date", "?")} - {w.get("end_date", "?")}): {w["description"]}'
            for w in resume_analysis.work_history
        )
        or "none listed"
    )
    education = (
        "; ".join(
            f'{e.get("degree", "")} {e.get("field_of_study", "")} - {e["institution"]} ({e.get("graduation_year", "?")})'
            for e in resume_analysis.education
        )
        or "none listed"
    )
    return {
        "job_title": jd_analysis.job_title or "",
        "role_context": jd_analysis.role_context or "",
        "responsibilities": "; ".join(jd_analysis.responsibilities),
        "qualifications": "; ".join(jd_analysis.qualifications),
        "skills_block": skills_block,
        "resume_summary": resume_analysis.summary or "",
        "total_experience_years": (
            str(resume_analysis.total_experience_years)
            if resume_analysis.total_experience_years is not None
            else "unknown"
        ),
        "resume_skills": resume_skills,
        "work_history": work_history,
        "education": education,
        "certifications": ", ".join(resume_analysis.certifications) or "none listed",
    }


async def create_submission(
    db: Session, jd_analysis: JDAnalysis, resume_analysis: ResumeAnalysis, actor: str, organization_id: uuid.UUID
) -> Submission:
    submission = Submission(
        organization_id=organization_id,
        submission_code=_next_submission_code(db),
        jd_analysis_id=jd_analysis.id,
        resume_analysis_id=resume_analysis.id,
        created_by=actor,
    )
    db.add(submission)
    db.flush()
    record_audit(db, "submission", submission.id, "created", actor)

    variables = _build_matching_variables(jd_analysis, resume_analysis)
    raw_output = await agent_client.invoke("MATCHING_AGENT", variables)
    match_result = LLMMatchAnalysis.model_validate(raw_output)
    match_result = _normalize_skill_match_weights(match_result)

    overall = (
        round(sum(m.jd_weight_percentage * m.match_percentage / 100 for m in match_result.skill_matches), 2)
        if match_result.skill_matches
        else match_result.overall_match_percentage
    )

    match_analysis = MatchAnalysis(
        submission_id=submission.id,
        overall_match_percentage=overall,
        skill_matches=[m.model_dump() for m in match_result.skill_matches],
        strengths=match_result.strengths,
        gaps=match_result.gaps,
        market_context_commentary=match_result.market_context_commentary,
        recommendation=match_result.recommendation,
        raw_llm_response=match_result.model_dump(),
    )
    db.add(match_analysis)
    db.commit()
    db.refresh(submission)
    logger.info("Submission %s created, overall match %.2f%%", submission.submission_code, overall)
    return submission


def soft_delete_submission(db: Session, submission: Submission, actor: str) -> Submission:
    submission.deleted_by = actor
    submission.deleted_at = datetime.now(timezone.utc)
    record_audit(db, "submission", submission.id, "deleted", actor)
    db.commit()
    db.refresh(submission)
    logger.info("Submission %s soft-deleted by %s", submission.submission_code, actor)
    return submission
