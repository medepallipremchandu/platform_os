import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import BadRequestError, ConflictError
from app.models.jd_analysis import JDAnalysis
from app.models.submission import Submission
from app.models.voice_call import JDCallAgentConfig, SubmissionCall
from app.schemas.voice_call import JDCallAgentConfigRequest
from app.services import voice_agent_client

logger = logging.getLogger("app.services.voice_call")

# Confirmed directly against the real voice-agent-service once it came up mid-build (see final
# report) - a live call's GET /calls/{id}.status came back as "FAILED" (uppercase), and its
# call-agent config's retry_on_statuses included "NO_ANSWER"/"BUSY" (also uppercase) - so the
# enum is upper-snake-case, not the lowercase guessed initially. is_terminal() compares
# case-insensitively as extra insurance. Any status not listed here is treated as non-terminal
# (safer to keep polling a little longer than to stop early and miss the real outcome) - if
# voice-agent-service adds a new terminal status later, add it here.
TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED", "NO_ANSWER", "VOICEMAIL", "BUSY", "ERROR"}


def is_terminal(status: str) -> bool:
    return status.upper() in TERMINAL_STATUSES


# --- JD call-agent configuration ---


def get_jd_call_config(db: Session, jd_analysis_id: uuid.UUID) -> JDCallAgentConfig | None:
    stmt = select(JDCallAgentConfig).where(JDCallAgentConfig.jd_analysis_id == jd_analysis_id)
    return db.execute(stmt).scalar_one_or_none()


def upsert_jd_call_config(
    db: Session, jd_analysis: JDAnalysis, payload: JDCallAgentConfigRequest, actor: str
) -> JDCallAgentConfig:
    config = get_jd_call_config(db, jd_analysis.id)
    if config is None:
        config = JDCallAgentConfig(
            jd_analysis_id=jd_analysis.id,
            call_agent_config_id=payload.call_agent_config_id,
            enabled=payload.enabled,
            created_by=actor,
        )
        db.add(config)
    else:
        config.call_agent_config_id = payload.call_agent_config_id
        config.enabled = payload.enabled
        config.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(config)
    logger.info(
        "JD %s call-agent config set to %s (enabled=%s) by %s",
        jd_analysis.jd_code,
        payload.call_agent_config_id,
        payload.enabled,
        actor,
    )
    return config


# --- Submission calls ---


def list_submission_calls(db: Session, submission_id: uuid.UUID) -> list[SubmissionCall]:
    stmt = (
        select(SubmissionCall)
        .where(SubmissionCall.submission_id == submission_id)
        .order_by(SubmissionCall.created_at)
    )
    return list(db.execute(stmt).scalars().all())


async def refresh_non_terminal_calls(db: Session, calls: list[SubmissionCall]) -> list[SubmissionCall]:
    """Best-effort lazy refresh: for any cached row still in a non-terminal state, re-fetch its
    real status from voice-agent-service (the source of truth) before returning it. This is what
    lets the frontend's ~10s poll of GET /submissions/{id}/calls actually reflect reality in local
    dev, where the webhook path can't be exercised end-to-end without a public tunnel - see
    app/api/webhooks.py and README. Swallows voice-agent-service errors and returns the
    last-known-cached row rather than failing the whole list."""
    changed = False
    for call in calls:
        if is_terminal(call.status):
            continue
        try:
            remote = await voice_agent_client.get_call(call.voice_agent_call_id)
        except Exception:
            logger.warning("Could not refresh live status for submission call %s", call.id, exc_info=True)
            continue
        remote_status = remote.get("status")
        if remote_status and remote_status != call.status:
            call.status = remote_status
            call.end_reason = remote.get("end_reason") or call.end_reason
            call.updated_at = datetime.now(timezone.utc)
            changed = True
            if is_terminal(remote_status):
                await _fetch_and_cache_summary(call)
    if changed:
        db.commit()
    return calls


async def _fetch_and_cache_summary(call: SubmissionCall) -> None:
    try:
        summary = await voice_agent_client.get_summary(call.voice_agent_call_id)
    except Exception:
        logger.warning("Could not fetch summary for submission call %s", call.id, exc_info=True)
        return
    if summary:
        call.summary_text = summary.get("summary_text")
        call.extracted_fields = summary.get("extracted_fields")


async def trigger_submission_call(db: Session, submission: Submission, actor: str) -> SubmissionCall:
    config = get_jd_call_config(db, submission.jd_analysis_id)
    if config is None:
        raise ConflictError("No call-agent config has been set for this submission's requirement yet.")
    if not config.enabled:
        raise ConflictError("AI phone screening is disabled for this submission's requirement.")

    candidate_phone = submission.resume_analysis.candidate_phone
    if not candidate_phone:
        raise BadRequestError("This candidate has no phone number on file.")

    existing = list_submission_calls(db, submission.id)
    attempt_number = len(existing) + 1

    submission_call = SubmissionCall(
        submission_id=submission.id,
        voice_agent_call_id="",  # filled in once voice-agent-service assigns one, below
        status="queued",
        attempt_number=attempt_number,
        triggered_by=actor,
    )
    db.add(submission_call)
    db.flush()  # assign submission_call.id so it can go into the webhook URL

    settings = get_settings()
    webhook_url = (
        f"{settings.PUBLIC_BASE_URL}/webhooks/voice-agent/{submission_call.id}"
        f"?secret={settings.VOICE_AGENT_WEBHOOK_SECRET}"
    )

    call = await voice_agent_client.create_call(
        call_agent_config_id=config.call_agent_config_id,
        to_number=candidate_phone,
        webhook_url=webhook_url,
        metadata={"submission_id": str(submission.id), "submission_call_id": str(submission_call.id)},
    )

    submission_call.voice_agent_call_id = str(call["id"])
    submission_call.status = call.get("status", "queued")
    submission_call.end_reason = call.get("end_reason")
    # Some calls fail synchronously (e.g. a provider-side rejection) fast enough that
    # POST /calls itself already returns a terminal status - don't wait on a webhook that may
    # never fire (or a next poll) to pick up the summary in that case.
    if is_terminal(submission_call.status):
        await _fetch_and_cache_summary(submission_call)
    db.commit()
    db.refresh(submission_call)
    logger.info(
        "Submission %s: triggered call attempt %d (voice_agent_call_id=%s) by %s",
        submission.id,
        attempt_number,
        submission_call.voice_agent_call_id,
        actor,
    )
    return submission_call


async def apply_webhook_update(db: Session, submission_call: SubmissionCall) -> SubmissionCall:
    """Re-fetches the call from voice-agent-service (the source of truth) rather than trusting
    the webhook payload's own status field - see app/api/webhooks.py."""
    remote = await voice_agent_client.get_call(submission_call.voice_agent_call_id)
    submission_call.status = remote.get("status", submission_call.status)
    submission_call.end_reason = remote.get("end_reason") or submission_call.end_reason
    submission_call.updated_at = datetime.now(timezone.utc)

    if is_terminal(submission_call.status):
        await _fetch_and_cache_summary(submission_call)

    db.commit()
    db.refresh(submission_call)
    return submission_call
