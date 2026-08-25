from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import CurrentActor, get_db, require_permission
from app.core.iam_client import post_audit_event
from app.core.permissions import CALLAGENTS_READ, CALLAGENTS_WRITE
from app.schemas.call_agents import (
    CallAgentConfigCreateRequest,
    CallAgentConfigListResponse,
    CallAgentConfigResponse,
    CallAgentConfigUpdateRequest,
)
from app.services import call_agents_service

router = APIRouter(prefix="/call-agents", tags=["call-agents"])


def _to_response(config) -> CallAgentConfigResponse:
    return CallAgentConfigResponse(
        id=config.id,
        organization_id=config.organization_id,
        name=config.name,
        description=config.description,
        persona=config.persona,
        objective=config.objective,
        consent_line=config.consent_line,
        closing_line=config.closing_line,
        fields=config.fields,
        max_conversation_duration_minutes=config.max_conversation_duration_minutes,
        retry_max_attempts=config.retry_max_attempts,
        retry_interval_minutes=config.retry_interval_minutes,
        retry_on_statuses=config.retry_on_statuses,
        telephony_provider_config_id=config.telephony_provider_config_id,
        visibility=config.visibility,
        is_active=config.is_active,
        created_by=config.created_by,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.post("", response_model=CallAgentConfigResponse, status_code=201)
async def create_call_agent(
    payload: CallAgentConfigCreateRequest,
    actor: CurrentActor = Depends(require_permission(CALLAGENTS_WRITE)),
    db: Session = Depends(get_db),
):
    config = call_agents_service.create_call_agent(db, actor, payload)
    await post_audit_event(
        actor.token, action="voiceagent.callagent.create", target_type="CallAgentConfig", target_id=str(config.id)
    )
    return _to_response(config)


@router.get("", response_model=CallAgentConfigListResponse)
async def list_call_agents(
    include_inactive: bool = False,
    actor: CurrentActor = Depends(require_permission(CALLAGENTS_READ)),
    db: Session = Depends(get_db),
):
    configs = call_agents_service.list_call_agents(db, actor, include_inactive)
    return CallAgentConfigListResponse(items=[_to_response(c) for c in configs])


@router.get("/{call_agent_config_id}", response_model=CallAgentConfigResponse)
async def get_call_agent(
    call_agent_config_id: uuid.UUID,
    actor: CurrentActor = Depends(require_permission(CALLAGENTS_READ)),
    db: Session = Depends(get_db),
):
    config = call_agents_service.get_call_agent(db, actor, call_agent_config_id)
    return _to_response(config)


@router.patch("/{call_agent_config_id}", response_model=CallAgentConfigResponse)
async def update_call_agent(
    call_agent_config_id: uuid.UUID,
    payload: CallAgentConfigUpdateRequest,
    actor: CurrentActor = Depends(require_permission(CALLAGENTS_WRITE)),
    db: Session = Depends(get_db),
):
    config = call_agents_service.update_call_agent(db, actor, call_agent_config_id, payload)
    await post_audit_event(
        actor.token, action="voiceagent.callagent.update", target_type="CallAgentConfig", target_id=str(config.id)
    )
    return _to_response(config)


@router.delete("/{call_agent_config_id}", response_model=CallAgentConfigResponse)
async def deactivate_call_agent(
    call_agent_config_id: uuid.UUID,
    actor: CurrentActor = Depends(require_permission(CALLAGENTS_WRITE)),
    db: Session = Depends(get_db),
):
    config = call_agents_service.deactivate_call_agent(db, actor, call_agent_config_id)
    await post_audit_event(
        actor.token, action="voiceagent.callagent.deactivate", target_type="CallAgentConfig", target_id=str(config.id)
    )
    return _to_response(config)
