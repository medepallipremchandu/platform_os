from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session, selectinload

from app.api.deps import CurrentActor, get_db, require_permission
from app.config import get_settings
from app.core import permissions
from app.core.exceptions import NotFoundError
from app.core.iam_client import post_audit_event
from app.models.agent import Agent
from app.models.invocation_log import AgentInvocationLog
from app.schemas.agent import (
    AgentCreateRequest,
    AgentCredentialOut,
    AgentOut,
    AgentSummary,
    AgentUpdateRequest,
    PublishResponse,
    RegenerateKeyResponse,
)
from app.schemas.invoke import InvocationLogOut
from app.services.agent_service import create_agent, publish_agent, regenerate_key, update_agent

router = APIRouter(prefix="/agents", tags=["agents"])


def _get_agent_or_404(db: Session, agent_id: UUID, organization_id) -> Agent:
    agent = (
        db.query(Agent)
        .options(selectinload(Agent.primary_model), selectinload(Agent.fallback_model), selectinload(Agent.credentials))
        .filter(Agent.id == agent_id, Agent.organization_id == organization_id)
        .first()
    )
    if agent is None:
        raise NotFoundError(f"Agent {agent_id} not found")
    return agent


@router.post("", response_model=AgentOut, status_code=201)
def create_agent_endpoint(
    payload: AgentCreateRequest,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(require_permission(permissions.AGENTS_WRITE)),
    authorization: str | None = Header(default=None),
):
    settings = get_settings()
    agent = create_agent(
        db,
        name=payload.name,
        description=payload.description,
        system_prompt=payload.system_prompt,
        user_prompt_template=payload.user_prompt_template,
        primary_model_id=payload.primary_model_id,
        fallback_model_id=payload.fallback_model_id,
        max_output_tokens=payload.max_output_tokens or settings.DEFAULT_MAX_OUTPUT_TOKENS,
        timeout_seconds=payload.timeout_seconds or settings.DEFAULT_TIMEOUT_SECONDS,
        rate_limit_per_minute=payload.rate_limit_per_minute or settings.DEFAULT_RATE_LIMIT_PER_MINUTE,
        actor=actor.email_or_name,
        organization_id=actor.org_id,
    )
    post_audit_event(authorization, action="agent.created", target_type="agent", target_id=agent.id)
    return _get_agent_or_404(db, agent.id, actor.org_id)


@router.get("", response_model=list[AgentSummary])
def list_agents(
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(require_permission(permissions.AGENTS_READ)),
):
    return (
        db.query(Agent)
        .options(selectinload(Agent.primary_model))
        .filter(Agent.organization_id == actor.org_id)
        .order_by(Agent.created_at.desc())
        .all()
    )


@router.get("/{agent_id}", response_model=AgentOut)
def get_agent(
    agent_id: UUID,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(require_permission(permissions.AGENTS_READ)),
):
    return _get_agent_or_404(db, agent_id, actor.org_id)


@router.patch("/{agent_id}", response_model=AgentOut)
def patch_agent(
    agent_id: UUID,
    payload: AgentUpdateRequest,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(require_permission(permissions.AGENTS_WRITE)),
    authorization: str | None = Header(default=None),
):
    agent = _get_agent_or_404(db, agent_id, actor.org_id)
    update_agent(db, agent, payload.model_dump(exclude_unset=True))
    post_audit_event(authorization, action="agent.updated", target_type="agent", target_id=agent.id)
    return _get_agent_or_404(db, agent_id, actor.org_id)


@router.post("/{agent_id}/publish", response_model=PublishResponse)
def publish_agent_endpoint(
    agent_id: UUID,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(require_permission(permissions.AGENTS_PUBLISH)),
    authorization: str | None = Header(default=None),
):
    agent = _get_agent_or_404(db, agent_id, actor.org_id)
    agent, plaintext_client_secret = publish_agent(db, agent, actor.email_or_name)
    post_audit_event(authorization, action="agent.published", target_type="agent", target_id=agent.id)
    return PublishResponse(agent=_get_agent_or_404(db, agent.id, actor.org_id), client_secret=plaintext_client_secret)


@router.post("/{agent_id}/keys/regenerate", response_model=RegenerateKeyResponse)
def regenerate_key_endpoint(
    agent_id: UUID,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(require_permission(permissions.AGENTS_MANAGE_KEYS)),
    authorization: str | None = Header(default=None),
):
    agent = _get_agent_or_404(db, agent_id, actor.org_id)
    plaintext_client_secret = regenerate_key(db, agent)
    post_audit_event(authorization, action="agent.credential_rotated", target_type="agent", target_id=agent.id)
    return RegenerateKeyResponse(client_secret=plaintext_client_secret)


@router.get("/{agent_id}/keys", response_model=list[AgentCredentialOut])
def list_agent_keys(
    agent_id: UUID,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(require_permission(permissions.AGENTS_MANAGE_KEYS)),
):
    agent = _get_agent_or_404(db, agent_id, actor.org_id)
    return agent.credentials


@router.get("/{agent_id}/usage", response_model=list[InvocationLogOut])
def get_agent_usage(
    agent_id: UUID,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(require_permission(permissions.AGENTS_READ)),
):
    _get_agent_or_404(db, agent_id, actor.org_id)
    return (
        db.query(AgentInvocationLog)
        .filter(AgentInvocationLog.agent_id == agent_id)
        .order_by(AgentInvocationLog.created_at.desc())
        .limit(100)
        .all()
    )
