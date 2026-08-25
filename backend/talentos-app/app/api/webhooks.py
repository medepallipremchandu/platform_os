"""Inbound webhook receiver(s) - called by other services, not by an interactive user, so these
routes are deliberately NOT registered under app.api.v1.router (which requires a valid IAM
bearer token on every route). They authenticate the caller a different way instead.

voice-agent-service posts a lifecycle event to the webhook_url we hand it at call-creation time
(POST /calls - see app/services/voice_call_service.py), best-effort/fire-and-forget from its
side. The exact payload shape wasn't independently verifiable while this was built (see final
report), so this handler treats the POST body as informational only: it never trusts the
payload's own `status` field, and instead re-fetches GET /calls/{id} (and, if now terminal,
GET /calls/{id}/summary) from voice-agent-service as the source of truth before updating the
cached SubmissionCall row - see app.services.voice_call_service.apply_webhook_update. Unknown or
extra fields on the body are ignored.

Security model: this route has no IAM bearer-token auth at all. The `?secret=` query param
(compared against VOICE_AGENT_WEBHOOK_SECRET) is the *only* gate against an inbound POST claiming
to be voice-agent-service - keep that secret out of logs/version control the same as any other
credential.
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.voice_call import SubmissionCall
from app.services import voice_call_service

logger = logging.getLogger("app.api.webhooks")

router = APIRouter(prefix="/webhooks/voice-agent", tags=["webhooks"])


@router.post("/{submission_call_id}", status_code=status.HTTP_204_NO_CONTENT)
async def receive_voice_agent_webhook(
    submission_call_id: UUID, request: Request, secret: str | None = None, db: Session = Depends(get_db)
):
    settings = get_settings()
    if not settings.VOICE_AGENT_WEBHOOK_SECRET or secret != settings.VOICE_AGENT_WEBHOOK_SECRET:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing webhook secret")

    try:
        body = await request.json()
    except Exception:
        body = None
    logger.info(
        "Received voice-agent webhook for submission_call=%s event_type=%s",
        submission_call_id,
        (body or {}).get("event_type") if isinstance(body, dict) else None,
    )

    submission_call = db.get(SubmissionCall, submission_call_id)
    if submission_call is None:
        # Not our concern to 4xx-and-retry-storm a best-effort webhook sender over a call we
        # don't (or no longer) know about - ack quietly.
        logger.warning("Webhook for unknown submission_call_id=%s - ignoring", submission_call_id)
        return None

    try:
        await voice_call_service.apply_webhook_update(db, submission_call)
    except Exception:
        logger.exception("Failed to apply webhook update for submission_call=%s", submission_call_id)
        # Still 204: voice-agent-service's delivery is best-effort/fire-and-forget: a failure
        # here shouldn't make it think the webhook needs retrying, since our own lazy-refresh-on-
        # read path (see voice_call_service.refresh_non_terminal_calls) will pick up the real
        # status on the next poll anyway.
    return None
