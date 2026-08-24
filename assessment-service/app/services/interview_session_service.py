import logging

from sqlalchemy.orm import Session

from app.models.interview_session import InterviewSession, Rubric, Skill
from app.services import intake_client

logger = logging.getLogger("app.services.interview_session")


async def get_or_create_interview_session(db: Session, submission_id) -> InterviewSession:
    """Idempotent: if this submission already has an interview session, return it unchanged
    (a submission's JD/skills don't change after the fact, so no need to re-snapshot)."""
    existing = db.query(InterviewSession).filter(InterviewSession.submission_id == submission_id).first()
    if existing is not None:
        return existing

    snapshot = await intake_client.fetch_submission_for_assessment(str(submission_id))

    session = InterviewSession(
        submission_id=snapshot["submission_id"],
        submission_code=snapshot["submission_code"],
        jd_code=snapshot["jd_code"],
        job_title=snapshot.get("job_title"),
        resume_code=snapshot["resume_code"],
        candidate_name=snapshot.get("candidate_name"),
    )
    for skill_data in snapshot["skills"]:
        skill = Skill(name=skill_data["name"], description=skill_data.get("description"))
        for rubric_data in skill_data["rubrics"]:
            skill.rubrics.append(
                Rubric(
                    name=rubric_data["name"],
                    description=rubric_data.get("description"),
                    weight_percentage=rubric_data["weight_percentage"],
                )
            )
        session.skills.append(skill)

    db.add(session)
    db.commit()
    db.refresh(session)
    logger.info(
        "Interview session %s created for submission %s with %d skills",
        session.id,
        session.submission_code,
        len(session.skills),
    )
    return session
