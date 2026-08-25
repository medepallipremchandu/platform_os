from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api.deps import CurrentActor, get_db, require_permission
from app.core.iam_client import post_audit_event
from app.core.permissions import CALLS_READ, CALLS_WRITE
from app.schemas.calls import (
    CallCreateRequest,
    CallEventResponse,
    CallListResponse,
    CallResponse,
    CallSummaryResponse,
    CancelCallRequest,
    ConversationTurnResponse,
)
from app.services import calls_service

router = APIRouter(prefix="/calls", tags=["calls"])


def _to_response(call) -> CallResponse:
    return CallResponse(
        id=call.id,
        organization_id=call.organization_id,
        call_agent_config_id=call.call_agent_config_id,
        telephony_provider_config_id=call.telephony_provider_config_id,
        status=call.status,
        to_number=call.to_number,
        from_number=call.from_number,
        max_duration_minutes=call.max_duration_minutes,
        webhook_url=call.webhook_url,
        metadata=call.metadata_json,
        extracted_fields=call.extracted_fields,
        consent_status=call.consent_status,
        end_reason=call.end_reason,
        retry_max_attempts=call.retry_max_attempts,
        retry_interval_minutes=call.retry_interval_minutes,
        retry_on_statuses=call.retry_on_statuses,
        attempt_number=call.attempt_number,
        root_call_id=call.root_call_id,
        next_retry_at=call.next_retry_at,
        created_by=call.created_by,
        created_at=call.created_at,
        connected_at=call.connected_at,
        ended_at=call.ended_at,
    )


@router.post("", response_model=CallResponse, status_code=202)
async def create_call(
    payload: CallCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    actor: CurrentActor = Depends(require_permission(CALLS_WRITE)),
    db: Session = Depends(get_db),
):
    call = await calls_service.create_call(db, actor, payload, idempotency_key)
    await post_audit_event(actor.token, action="voiceagent.call.create", target_type="Call", target_id=str(call.id))
    return _to_response(call)


@router.get("", response_model=CallListResponse)
async def list_calls(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    search: str | None = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    actor: CurrentActor = Depends(require_permission(CALLS_READ)),
    db: Session = Depends(get_db),
):
    calls, total = calls_service.list_calls(db, actor, limit, offset, status, search, sort_by, sort_dir)
    return CallListResponse(items=[_to_response(c) for c in calls], total=total, limit=limit, offset=offset)


@router.get("/{call_id}", response_model=CallResponse)
async def get_call(
    call_id: uuid.UUID,
    actor: CurrentActor = Depends(require_permission(CALLS_READ)),
    db: Session = Depends(get_db),
):
    call = calls_service.get_call(db, actor, call_id)
    return _to_response(call)


@router.get("/{call_id}/events", response_model=list[CallEventResponse])
async def get_call_events(
    call_id: uuid.UUID,
    actor: CurrentActor = Depends(require_permission(CALLS_READ)),
    db: Session = Depends(get_db),
):
    call = calls_service.get_call(db, actor, call_id)
    events = calls_service.get_events(db, call)
    return [
        CallEventResponse(id=e.id, event_type=e.event_type, payload=e.payload, created_at=e.created_at)
        for e in events
    ]


@router.get("/{call_id}/conversation", response_model=list[ConversationTurnResponse])
async def get_call_conversation(
    call_id: uuid.UUID,
    actor: CurrentActor = Depends(require_permission(CALLS_READ)),
    db: Session = Depends(get_db),
):
    call = calls_service.get_call(db, actor, call_id)
    turns = calls_service.get_conversation(db, call)
    return [
        ConversationTurnResponse(turn_index=t.turn_index, speaker=t.speaker, text=t.text, created_at=t.created_at)
        for t in turns
    ]


@router.get("/{call_id}/summary", response_model=CallSummaryResponse | None)
async def get_call_summary(
    call_id: uuid.UUID,
    actor: CurrentActor = Depends(require_permission(CALLS_READ)),
    db: Session = Depends(get_db),
):
    call = calls_service.get_call(db, actor, call_id)
    summary = calls_service.get_summary(db, call)
    if summary is None:
        return None
    return CallSummaryResponse(
        summary_text=summary.summary_text, extracted_fields=summary.extracted_fields, created_at=summary.created_at
    )


@router.post("/{call_id}/cancel", response_model=CallResponse)
async def cancel_call(
    call_id: uuid.UUID,
    payload: CancelCallRequest,
    actor: CurrentActor = Depends(require_permission(CALLS_WRITE)),
    db: Session = Depends(get_db),
):
    call = calls_service.get_call(db, actor, call_id)
    call = calls_service.cancel_call(db, call, payload.graceful)
    await post_audit_event(actor.token, action="voiceagent.call.cancel", target_type="Call", target_id=str(call.id))
    return _to_response(call)
