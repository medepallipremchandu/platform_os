"""Twilio's callback endpoints driving the turn loop. Ported from the reference
implementation's app/routers/webhooks.py: same single-endpoint-drives-the-whole-conversation
design (branch on `call.status`, no separate in-memory session), same consent-gather ->
main-conversation-turns -> wrap-up orchestration - but calling app.services.conversation_client
(agent-builder-service) instead of the old direct-AI-provider ConversationService.

Authenticated by Twilio's X-Twilio-Signature (verified against the organization's stored,
decrypted Twilio auth token), NOT an IAM Bearer token - Twilio itself calls these, not an
end-user or another service acting on a user's behalf. Because there's no inbound bearer token
to attribute an audit event to, these two routes post their (best-effort) audit events using
this service's own machine identity (see app/core/iam_client.get_service_token) - i.e. as a
system actor, once per webhook request.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Gather, VoiceResponse

from app.api.deps import get_db
from app.config import get_settings
from app.core.crypto import decrypt_credentials
from app.core.exceptions import ConversationAgentError
from app.core.iam_client import get_service_token, post_audit_event
from app.core.state_machine import TERMINAL_STATES, CallStatus
from app.models.call import Call, CallSummary, ConversationTurn
from app.services import calls_service, conversation_client, providers_service

router = APIRouter(prefix="/webhooks/twilio", tags=["webhooks"])
logger = logging.getLogger("app.api.webhooks")

MAX_SILENCE_RETRIES = 2
MAX_CONSENT_RETRIES = 3
WARNING_2MIN_SECONDS = 120
WARNING_1MIN_SECONDS = 60


async def _audit_system(action: str, call: Call) -> None:
    try:
        token = await get_service_token()
    except Exception:
        logger.debug("Skipping system audit event %s for call %s - no service token available", action, call.id)
        return
    await post_audit_event(token, action=action, target_type="Call", target_id=str(call.id))


def _load_call_or_404(db: Session, call_id: uuid.UUID) -> Call:
    call = db.execute(select(Call).where(Call.id == call_id)).scalar_one_or_none()
    if call is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown call")
    return call


async def _verify_twilio_signature(request: Request, db: Session, call: Call) -> None:
    provider_config = providers_service.get_provider_for_call(
        db, call.organization_id, call.telephony_provider_config_id
    )
    creds = decrypt_credentials(provider_config.encrypted_credentials)
    validator = RequestValidator(creds["authToken"])

    form = await request.form()
    signature = request.headers.get("X-Twilio-Signature", "")
    settings = get_settings()
    url = f"{settings.BASE_URL}{request.url.path}"

    if not validator.validate(url, dict(form), signature):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Invalid Twilio signature")


def _append_turn(db: Session, call: Call, speaker: str, text: str) -> None:
    existing = list(db.execute(select(ConversationTurn.turn_index).where(ConversationTurn.call_id == call.id)).scalars().all())
    next_index = max(existing, default=-1) + 1
    db.add(ConversationTurn(call_id=call.id, turn_index=next_index, speaker=speaker, text=text))
    db.flush()


def _history(db: Session, call: Call) -> list[dict]:
    result = db.execute(
        select(ConversationTurn).where(ConversationTurn.call_id == call.id).order_by(ConversationTurn.turn_index)
    )
    return [{"speaker": t.speaker, "text": t.text} for t in result.scalars().all()]


def _say_and_gather(action_url: str, say_text: str) -> str:
    vr = VoiceResponse()
    vr.say(say_text)
    gather = Gather(input="speech", action=action_url, method="POST", speech_timeout="auto", timeout=6)
    vr.append(gather)
    vr.redirect(action_url, method="POST")
    return str(vr)


def _say_and_hangup(say_text: str) -> str:
    vr = VoiceResponse()
    vr.say(say_text)
    vr.hangup()
    return str(vr)


async def _finish_with_summary(db: Session, call: Call, end_reason: str) -> str:
    history = _history(db, call)
    script = call.call_script
    try:
        result = await conversation_client.generate_summary(
            persona=script["persona"], objective=script["objective"], history=history, extracted_fields=call.extracted_fields
        )
        summary_text = result.get("summary_text", "")
        final_fields = result.get("extracted_fields", call.extracted_fields)
    except ConversationAgentError:
        summary_text = "Summary unavailable - AI summarization failed after call completion."
        final_fields = call.extracted_fields

    db.add(CallSummary(call_id=call.id, summary_text=summary_text, extracted_fields=final_fields))
    call.extracted_fields = final_fields
    calls_service.log_event(db, call, "SUMMARY_GENERATED", {"summary_text": summary_text})
    calls_service.transition(db, call, CallStatus.COMPLETED, "CALL_COMPLETED", {"end_reason": end_reason})
    call.end_reason = end_reason
    return _say_and_hangup(script["closing_line"])


@router.post("/voice/{call_id}")
async def voice_and_gather(call_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    """Single endpoint for the entire in-call turn loop.

    Twilio hits this once on answer (no SpeechResult) and again after every <Gather> - either
    with a SpeechResult, or via the trailing <Redirect> when the callee stayed silent. Branching
    on `call.status` tells us which stage of the conversation we're in; there is no separate
    in-memory session.
    """
    call = _load_call_or_404(db, call_id)
    await _verify_twilio_signature(request, db, call)

    form = await request.form()
    speech_result = (form.get("SpeechResult") or "").strip()
    action_url = f"{get_settings().BASE_URL}/webhooks/twilio/voice/{call_id}"
    script = call.call_script

    # First hit for this call: mark connected and open with the consent ask.
    if CallStatus(call.status) in {CallStatus.DIALING, CallStatus.RINGING}:
        calls_service.transition(db, call, CallStatus.CONNECTED, "CALL_CONNECTED")
        calls_service.transition(db, call, CallStatus.CONSENT_PENDING, "CONSENT_REQUESTED")
        _append_turn(db, call, "ai", script["consent_line"])
        db.commit()
        await _audit_system("voiceagent.call.connected", call)
        return Response(content=_say_and_gather(action_url, script["consent_line"]), media_type="application/xml")

    if not speech_result:
        call.silence_count += 1
        if call.silence_count > MAX_SILENCE_RETRIES:
            calls_service.transition(
                db, call, CallStatus.DISCONNECTED, "CALL_DISCONNECTED", {"reason": "callee_unresponsive"}
            )
            call.end_reason = "CALLEE_UNRESPONSIVE"
            db.commit()
            await _audit_system("voiceagent.call.turn", call)
            return Response(content=_say_and_hangup("We haven't heard from you, goodbye."), media_type="application/xml")
        db.commit()
        return Response(
            content=_say_and_gather(action_url, "Sorry, I didn't catch that. Could you say that again?"),
            media_type="application/xml",
        )
    call.silence_count = 0
    _append_turn(db, call, "callee", speech_result)

    if CallStatus(call.status) == CallStatus.CONSENT_PENDING:
        try:
            result = await conversation_client.consent_turn(
                persona=script["persona"], consent_line=script["consent_line"], callee_speech=speech_result
            )
        except ConversationAgentError:
            result = {"consent": "unclear", "ai_response": ""}
        consent = (result.get("consent") or "unclear").lower()

        if consent == "yes":
            call.consent_status = "granted"
            calls_service.transition(db, call, CallStatus.CONVERSATION, "CONSENT_GRANTED")
            # Templated, not an LLM call - the caller is already waiting on the consent_turn()
            # round trip above; a second LLM call back-to-back here would double the latency of
            # this one turn for no benefit, since the objective is fixed, tenant-authored text.
            opening_line = f"Great, thank you. {script['objective']}"
            _append_turn(db, call, "ai", opening_line)
            db.commit()
            await _audit_system("voiceagent.call.turn", call)
            return Response(content=_say_and_gather(action_url, opening_line), media_type="application/xml")

        if consent == "no":
            call.consent_status = "denied"
            calls_service.transition(db, call, CallStatus.CONSENT_DENIED, "CONSENT_DENIED")
            call.end_reason = "CONSENT_DENIED"
            db.commit()
            await _audit_system("voiceagent.call.turn", call)
            return Response(content=_say_and_hangup(script["closing_line"]), media_type="application/xml")

        call.consent_retry_count += 1
        if call.consent_retry_count > MAX_CONSENT_RETRIES:
            call.consent_status = "denied"
            calls_service.transition(
                db, call, CallStatus.CONSENT_DENIED, "CONSENT_DENIED", {"reason": "no_clear_response"}
            )
            call.end_reason = "CONSENT_UNCLEAR_EXHAUSTED_RETRIES"
            db.commit()
            await _audit_system("voiceagent.call.turn", call)
            return Response(content=_say_and_hangup(script["closing_line"]), media_type="application/xml")

        ai_response = result.get("ai_response") or "Sorry, I didn't quite catch that - do you consent to continue?"
        _append_turn(db, call, "ai", ai_response)
        db.commit()
        return Response(content=_say_and_gather(action_url, ai_response), media_type="application/xml")

    if CallStatus(call.status) == CallStatus.CONVERSATION:
        elapsed_seconds = (datetime.now(timezone.utc) - call.connected_at).total_seconds()
        remaining_seconds = call.max_duration_minutes * 60 - elapsed_seconds

        if remaining_seconds <= 0:
            calls_service.transition(db, call, CallStatus.SUMMARY, "CALL_TIME_LIMIT_REACHED")
            twiml = await _finish_with_summary(db, call, end_reason="TIME_LIMIT_REACHED")
            db.commit()
            await _audit_system("voiceagent.call.completed", call)
            return Response(content=twiml, media_type="application/xml")

        time_notice = None
        if remaining_seconds <= WARNING_1MIN_SECONDS and not call.warned_1min:
            call.warned_1min = True
            time_notice = "Just one more minute left, so let's wrap up shortly."
            calls_service.log_event(db, call, "TIME_WARNING", {"remaining_seconds": remaining_seconds, "warning": "1min"})
        elif remaining_seconds <= WARNING_2MIN_SECONDS and not call.warned_2min:
            call.warned_2min = True
            time_notice = (
                "Just a quick note - we have about two minutes left in our conversation. "
                "I'll make sure we capture anything important before we wrap up."
            )
            calls_service.log_event(db, call, "TIME_WARNING", {"remaining_seconds": remaining_seconds, "warning": "2min"})

        try:
            result = await conversation_client.main_turn(
                persona=script["persona"],
                objective=script["objective"],
                fields=script["fields"],
                closing_line=script["closing_line"],
                history=_history(db, call),
                callee_speech=speech_result,
                time_notice=time_notice,
            )
        except ConversationAgentError:
            result = {"ai_response": "Sorry, could you repeat that?", "fields": {}, "done": False}

        new_fields = {k: v for k, v in (result.get("fields") or {}).items() if v}
        if new_fields:
            call.extracted_fields = {**call.extracted_fields, **new_fields}

        ai_response = result.get("ai_response", "")
        _append_turn(db, call, "ai", ai_response)

        if result.get("done"):
            calls_service.transition(db, call, CallStatus.SUMMARY, "CALL_OBJECTIVE_COMPLETE")
            twiml = await _finish_with_summary(db, call, end_reason="OBJECTIVE_COMPLETE")
            db.commit()
            await _audit_system("voiceagent.call.completed", call)
            return Response(content=twiml, media_type="application/xml")

        db.commit()
        return Response(content=_say_and_gather(action_url, ai_response), media_type="application/xml")

    # Call already in a terminal or otherwise unexpected state - end gracefully.
    db.commit()
    return Response(content=_say_and_hangup(script["closing_line"]), media_type="application/xml")


@router.post("/status/{call_id}")
async def call_status(call_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    call = _load_call_or_404(db, call_id)
    await _verify_twilio_signature(request, db, call)

    form = await request.form()
    twilio_status = (form.get("CallStatus") or "").lower()

    transition_map = {
        "ringing": (CallStatus.RINGING, "CALL_RINGING"),
        "busy": (CallStatus.BUSY, "CALL_BUSY"),
        "no-answer": (CallStatus.NO_ANSWER, "CALL_NO_ANSWER"),
        "failed": (CallStatus.FAILED, "CALL_FAILED"),
        "canceled": (CallStatus.CANCELLED, "CALL_CANCELLED"),
        "completed": (CallStatus.DISCONNECTED, "CALL_DISCONNECTED"),
    }
    target = transition_map.get(twilio_status)
    if target is not None and CallStatus(call.status) not in TERMINAL_STATES:
        try:
            calls_service.transition(db, call, target[0], target[1], {"provider_status": twilio_status})
            if target[0] != CallStatus.RINGING:
                call.end_reason = call.end_reason or target[0].value
        except Exception:
            # Duplicate/out-of-order provider webhook racing our own turn logic - already-terminal
            # or not-yet-reachable target is a no-op, not an error.
            calls_service.log_event(db, call, "PROVIDER_STATUS_IGNORED", {"provider_status": twilio_status})
    else:
        calls_service.log_event(db, call, "PROVIDER_STATUS_RECEIVED", {"provider_status": twilio_status})

    db.commit()
    await _audit_system("voiceagent.call.provider_status", call)
    return Response(status_code=204)
