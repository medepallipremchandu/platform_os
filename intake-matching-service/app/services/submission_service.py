import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.jd_analysis import JDAnalysis
from app.models.resume_analysis import ResumeAnalysis
from app.models.submission import MatchAnalysis, Submission
from app.prompts.matching_prompt import build_matching_prompt
from app.schemas.llm_outputs import LLMMatchAnalysis
from app.services.audit_service import record_audit
from app.services.llm.llm_client import LLMClient

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


async def create_submission(
    db: Session, jd_analysis: JDAnalysis, resume_analysis: ResumeAnalysis, llm_client: LLMClient, actor: str
) -> Submission:
    submission = Submission(
        submission_code=_next_submission_code(db),
        jd_analysis_id=jd_analysis.id,
        resume_analysis_id=resume_analysis.id,
        created_by=actor,
    )
    db.add(submission)
    db.flush()
    record_audit(db, "submission", submission.id, "created", actor)

    skills_payload = [
        {
            "name": s.name,
            "description": s.description or "",
            "rubrics": [{"name": r.name, "weight_percentage": float(r.weight_percentage)} for r in s.rubrics],
        }
        for s in jd_analysis.skills
    ]
    system_prompt, user_prompt = build_matching_prompt(
        job_title=jd_analysis.job_title or "",
        role_context=jd_analysis.role_context or "",
        responsibilities=jd_analysis.responsibilities,
        qualifications=jd_analysis.qualifications,
        skills=skills_payload,
        resume_summary=resume_analysis.summary or "",
        total_experience_years=(
            float(resume_analysis.total_experience_years)
            if resume_analysis.total_experience_years is not None
            else None
        ),
        resume_skills=resume_analysis.skills,
        work_history=resume_analysis.work_history,
        education=resume_analysis.education,
        certifications=resume_analysis.certifications,
    )
    match_result: LLMMatchAnalysis = await llm_client.get_json(system_prompt, user_prompt, LLMMatchAnalysis)
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
