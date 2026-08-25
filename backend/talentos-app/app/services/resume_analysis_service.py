import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.resume_analysis import ResumeAnalysis
from app.schemas.llm_outputs import LLMResumeExtraction
from app.schemas.resume_analysis import ResumeAnalysisUpdateRequest
from app.services import agent_client, file_parsing_service
from app.services.audit_service import record_audit

logger = logging.getLogger("app.services.resume_analysis")

_UPDATABLE_FIELDS = ("candidate_name", "candidate_email", "candidate_phone", "total_experience_years", "summary")


def _next_resume_code(db: Session) -> str:
    seq_value = db.execute(text("SELECT nextval('resume_code_seq')")).scalar_one()
    return f"RES{seq_value:02d}"


async def analyze_resume(
    db: Session, filename: str, file_bytes: bytes, actor: str, organization_id: uuid.UUID
) -> ResumeAnalysis:
    resume_text, file_type = file_parsing_service.extract_text(filename, file_bytes)

    raw_output = await agent_client.invoke("RESUME_ANALYSIS_AGENT", {"resume_text": resume_text})
    extraction = LLMResumeExtraction.model_validate(raw_output)

    resume_analysis = ResumeAnalysis(
        organization_id=organization_id,
        resume_code=_next_resume_code(db),
        original_filename=filename,
        file_type=file_type,
        raw_text=resume_text,
        candidate_name=extraction.candidate_name,
        candidate_email=extraction.candidate_email,
        candidate_phone=extraction.candidate_phone,
        total_experience_years=extraction.total_experience_years,
        summary=extraction.summary,
        skills=[s.model_dump() for s in extraction.skills],
        work_history=[w.model_dump() for w in extraction.work_history],
        education=[e.model_dump() for e in extraction.education],
        certifications=extraction.certifications,
        raw_llm_response=extraction.model_dump(),
        created_by=actor,
    )

    db.add(resume_analysis)
    db.flush()
    record_audit(db, "resume_analysis", resume_analysis.id, "created", actor)
    db.commit()
    db.refresh(resume_analysis)
    logger.info(
        "Resume analysis %s (%s) created for %s",
        resume_analysis.resume_code,
        resume_analysis.id,
        resume_analysis.candidate_name,
    )
    return resume_analysis


def update_resume_analysis(
    db: Session, resume_analysis: ResumeAnalysis, payload: ResumeAnalysisUpdateRequest, actor: str
) -> ResumeAnalysis:
    """Mirrors jd_analysis_service.update_jd_analysis exactly: diff -> stamp modified_by/at ->
    audit -> commit, only for the fields ResumeAnalysisUpdateRequest exposes."""
    changes: dict[str, dict] = {}
    for field in _UPDATABLE_FIELDS:
        new_value = getattr(payload, field)
        if new_value is None:
            continue
        old_value = getattr(resume_analysis, field)
        if field == "total_experience_years" and old_value is not None:
            old_value = float(old_value)
        if old_value != new_value:
            changes[field] = {"old": old_value, "new": new_value}
            setattr(resume_analysis, field, new_value)

    if changes:
        resume_analysis.modified_by = actor
        resume_analysis.modified_at = datetime.now(timezone.utc)
        record_audit(db, "resume_analysis", resume_analysis.id, "updated", actor, changes)
        db.commit()
        db.refresh(resume_analysis)
        logger.info("Resume analysis %s updated by %s: %s", resume_analysis.resume_code, actor, list(changes.keys()))
    return resume_analysis


def soft_delete_resume_analysis(db: Session, resume_analysis: ResumeAnalysis, actor: str) -> ResumeAnalysis:
    resume_analysis.deleted_by = actor
    resume_analysis.deleted_at = datetime.now(timezone.utc)
    record_audit(db, "resume_analysis", resume_analysis.id, "deleted", actor)
    db.commit()
    db.refresh(resume_analysis)
    logger.info("Resume analysis %s soft-deleted by %s", resume_analysis.resume_code, actor)
    return resume_analysis
