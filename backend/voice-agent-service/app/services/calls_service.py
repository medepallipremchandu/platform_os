from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.crypto import decrypt_credentials
from app.core.exceptions import ConflictError, NotFoundError
from app.core.iam_client import CurrentActor
from app.core.state_machine import TERMINAL_STATES, CallStatus, validate_transition
from app.models.call import Call, CallEvent, CallSummary, ConversationTurn, IdempotencyKey
from app.providers.telephony import get_telephony_provider
from app.schemas.calls import CallCreateRequest
from app.services import call_agents_service, providers_service

logger = logging.getLogger("app.services.calls")


def log_event(db: Session, call: Call, event_type: str, payload: dict | None = None) -> CallEvent:
    event = CallEvent(call_id=call.id, event_type=event_type, payload=payload or {})
    db.add(event)
    db.flush()
    return event


def _maybe_schedule_retry(call: Call, target: CallStatus) -> None:
    """Called the instant a Call reaches a terminal state that is ALSO one of this call's own
    retry_on_statuses AND attempt_number < retry_max_attempts: stamps next_retry_at - the
    background poller (app/services/retry_poller.py) picks it up from there and clears it once
    the retry has actually fired."""
    if target.value not in (call.retry_on_statuses or []):
        return
    if call.attempt_number >= call.retry_max_attempts:
        return
    call.next_retry_at = datetime.now(timezone.utc) + timedelta(minutes=call.retry_interval_minutes)


def transition(db: Session, call: Call, target: CallStatus, event_type: str, payload: dict | None = None) -> None:
    """Copied/extended from the reference implementation's services/calls.transition(): same
    validated state-machine transition + event log, plus retry scheduling the moment a call
    lands in a terminal state."""
    validate_transition(CallStatus(call.status), target)
    call.status = target.value
    if target == CallStatus.CONNECTED:
        call.connected_at = datetime.now(timezone.utc)
    if target in TERMINAL_STATES:
        call.ended_at = datetime.now(timezone.utc)
        _maybe_schedule_retry(call, target)
    log_event(db, call, event_type, payload)
    db.flush()


async def dial(db: Session, call: Call, provider_name: str, provider_creds: dict) -> None:
    """Places the outbound call through the telephony provider and transitions
    QUEUED -> DIALING (or -> FAILED on a provider/network error). Shared by create_call (first
    attempt) and the retry poller (subsequent attempts)."""
    settings = get_settings()
    try:
        telephony = get_telephony_provider(provider_name, provider_creds)
        provider_call_sid = await telephony.place_call(
            to_number=call.to_number, from_number=call.from_number, call_id=call.id, base_url=settings.BASE_URL
        )
        call.provider_call_sid = provider_call_sid
        transition(db, call, CallStatus.DIALING, "CALL_DIALING", {"provider_call_sid": provider_call_sid})
    except Exception as exc:  # provider/network failure placing the call
        logger.error("Failed to place call %s via %s: %s", call.id, provider_name, exc)
        transition(db, call, CallStatus.FAILED, "CALL_FAILED", {"reason": str(exc)})
        call.end_reason = "PROVIDER_ERROR"


async def create_call(
    db: Session, actor: CurrentActor, payload: CallCreateRequest, idempotency_key: str | None
) -> Call:
    organization_id = uuid.UUID(actor.org_id)

    if idempotency_key:
        existing = db.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.organization_id == organization_id, IdempotencyKey.key == idempotency_key
            )
        ).scalar_one_or_none()
        if existing is not None:
            return db.execute(select(Call).where(Call.id == existing.call_id)).scalar_one()

    if payload.call_agent_config_id is not None:
        agent_config = call_agents_service.get_call_agent(db, actor, payload.call_agent_config_id)
        if not agent_config.is_active:
            raise ConflictError("Call agent config is not active")
        telephony_provider_config_id = agent_config.telephony_provider_config_id
        call_script = {
            "persona": agent_config.persona,
            "objective": agent_config.objective,
            "consent_line": agent_config.consent_line,
            "closing_line": agent_config.closing_line,
            "fields": agent_config.fields,
        }
        max_duration = agent_config.max_conversation_duration_minutes
        retry_max_attempts = agent_config.retry_max_attempts
        retry_interval_minutes = agent_config.retry_interval_minutes
        retry_on_statuses = list(agent_config.retry_on_statuses or [])
    else:
        # Fully inline, ad-hoc call - no saved config, so no retry policy to carry:
        # retry_max_attempts defaults to 0 (never retried).
        providers_service.get_provider(db, actor, payload.telephony_provider_config_id)
        telephony_provider_config_id = payload.telephony_provider_config_id
        call_script = payload.call_script.model_dump()
        max_duration = payload.max_conversation_duration_minutes
        retry_max_attempts = 0
        retry_interval_minutes = 30
        retry_on_statuses = ["NO_ANSWER", "BUSY"]

    provider_config = providers_service.get_provider_for_call(db, organization_id, telephony_provider_config_id)
    provider_creds = decrypt_credentials(provider_config.encrypted_credentials)

    call = Call(
        organization_id=organization_id,
        call_agent_config_id=payload.call_agent_config_id,
        telephony_provider_config_id=telephony_provider_config_id,
        to_number=payload.to_number,
        from_number=provider_config.phone_number,
        status=CallStatus.CREATED.value,
        max_duration_minutes=max_duration,
        call_script=call_script,
        webhook_url=payload.webhook_url,
        metadata_json=payload.metadata,
        retry_max_attempts=retry_max_attempts,
        retry_interval_minutes=retry_interval_minutes,
        retry_on_statuses=retry_on_statuses,
        attempt_number=1,
        created_by=actor.email_or_name,
    )
    db.add(call)
    db.flush()
    log_event(db, call, "CALL_CREATED", {"to_number": payload.to_number})

    if idempotency_key:
        db.add(IdempotencyKey(organization_id=organization_id, key=idempotency_key, call_id=call.id))

    transition(db, call, CallStatus.QUEUED, "CALL_QUEUED")
    db.commit()

    await dial(db, call, provider_config.provider, provider_creds)

    db.commit()
    db.refresh(call)
    return call


def get_call(db: Session, actor: CurrentActor, call_id: uuid.UUID) -> Call:
    result = db.execute(select(Call).where(Call.id == call_id, Call.organization_id == uuid.UUID(actor.org_id)))
    call = result.scalar_one_or_none()
    if call is None:
        raise NotFoundError("Call not found")
    return call


# Columns a caller may sort `GET /calls` by - an explicit allowlist so `sort_by` can never be used
# to inject an arbitrary column/expression into the ORDER BY clause.
_SORTABLE_CALL_COLUMNS = {
    "created_at": Call.created_at,
    "status": Call.status,
    "attempt_number": Call.attempt_number,
}


def list_calls(
    db: Session,
    actor: CurrentActor,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    search: str | None = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> tuple[list[Call], int]:
    base = select(Call).where(Call.organization_id == uuid.UUID(actor.org_id))
    if status:
        base = base.where(Call.status == status)
    if search:
        base = base.where(Call.to_number.ilike(f"%{search}%"))
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()

    column = _SORTABLE_CALL_COLUMNS.get(sort_by, Call.created_at)
    order = column.asc() if sort_dir == "asc" else column.desc()
    result = db.execute(base.order_by(order).offset(offset).limit(limit))
    return list(result.scalars().all()), total


def get_events(db: Session, call: Call) -> list[CallEvent]:
    result = db.execute(select(CallEvent).where(CallEvent.call_id == call.id).order_by(CallEvent.created_at))
    return list(result.scalars().all())


def get_conversation(db: Session, call: Call) -> list[ConversationTurn]:
    result = db.execute(
        select(ConversationTurn).where(ConversationTurn.call_id == call.id).order_by(ConversationTurn.turn_index)
    )
    return list(result.scalars().all())


def get_summary(db: Session, call: Call) -> CallSummary | None:
    result = db.execute(select(CallSummary).where(CallSummary.call_id == call.id))
    return result.scalar_one_or_none()


def cancel_call(db: Session, call: Call, graceful: bool) -> Call:
    if CallStatus(call.status) in TERMINAL_STATES:
        raise ConflictError(f"Call already in terminal state {call.status}")

    transition(db, call, CallStatus.CANCELLED, "CALL_CANCELLED", {"graceful": graceful})
    call.end_reason = "CANCELLED_BY_TENANT"
    db.commit()
    db.refresh(call)
    return call
