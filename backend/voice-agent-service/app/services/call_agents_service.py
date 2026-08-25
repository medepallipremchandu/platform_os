from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.iam_client import CurrentActor
from app.models.call_agent import CallAgentConfig, CallAgentConfigGrant
from app.schemas.call_agents import CallAgentConfigCreateRequest, CallAgentConfigUpdateRequest
from app.services.providers_service import get_provider
from app.services.visibility import visible_query


def create_call_agent(db: Session, actor: CurrentActor, payload: CallAgentConfigCreateRequest) -> CallAgentConfig:
    # Confirms the provider exists and is visible to this actor (revoked/inaccessible providers
    # can't be bound to a new call agent config).
    get_provider(db, actor, payload.telephony_provider_config_id)

    config = CallAgentConfig(
        organization_id=uuid.UUID(actor.org_id),
        name=payload.name,
        description=payload.description,
        persona=payload.persona,
        objective=payload.objective,
        consent_line=payload.consent_line,
        closing_line=payload.closing_line,
        fields=[f.model_dump() for f in payload.fields],
        max_conversation_duration_minutes=payload.max_conversation_duration_minutes,
        retry_max_attempts=payload.retry_max_attempts,
        retry_interval_minutes=payload.retry_interval_minutes,
        retry_on_statuses=payload.retry_on_statuses,
        telephony_provider_config_id=payload.telephony_provider_config_id,
        visibility=payload.visibility,
        created_by=actor.email_or_name,
    )
    db.add(config)
    db.flush()

    if payload.visibility == "restricted":
        for user_id in payload.grant_user_ids:
            db.add(CallAgentConfigGrant(call_agent_config_id=config.id, user_id=user_id))

    db.commit()
    db.refresh(config)
    return config


def list_call_agents(db: Session, actor: CurrentActor, include_inactive: bool = False) -> list[CallAgentConfig]:
    query = visible_query(db, CallAgentConfig, CallAgentConfigGrant, CallAgentConfigGrant.call_agent_config_id, actor)
    if not include_inactive:
        query = query.where(CallAgentConfig.is_active.is_(True))
    return list(db.execute(query.order_by(CallAgentConfig.created_at.desc())).scalars().all())


def get_call_agent(db: Session, actor: CurrentActor, config_id: uuid.UUID) -> CallAgentConfig:
    query = visible_query(
        db, CallAgentConfig, CallAgentConfigGrant, CallAgentConfigGrant.call_agent_config_id, actor
    ).where(CallAgentConfig.id == config_id)
    config = db.execute(query).scalar_one_or_none()
    if config is None:
        raise NotFoundError("Call agent config not found")
    return config


def get_call_agent_for_call(db: Session, organization_id: uuid.UUID, config_id: uuid.UUID) -> CallAgentConfig:
    """Org-scoped only (no visibility filtering) - a caller placing a call via
    call_agent_config_id must already be able to see the config (enforced at the API layer via
    get_call_agent before create_call is invoked); this helper is for internal reuse (e.g. the
    retry poller) that already trusts the organization scoping."""
    from sqlalchemy import select

    result = db.execute(
        select(CallAgentConfig).where(CallAgentConfig.id == config_id, CallAgentConfig.organization_id == organization_id)
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise NotFoundError("Call agent config not found")
    return config


_UPDATABLE_FIELDS = (
    "name",
    "description",
    "persona",
    "objective",
    "consent_line",
    "closing_line",
    "max_conversation_duration_minutes",
    "retry_max_attempts",
    "retry_interval_minutes",
    "retry_on_statuses",
    "telephony_provider_config_id",
    "visibility",
    "is_active",
)


def update_call_agent(
    db: Session, actor: CurrentActor, config_id: uuid.UUID, payload: CallAgentConfigUpdateRequest
) -> CallAgentConfig:
    config = get_call_agent(db, actor, config_id)
    updates = payload.model_dump(exclude_unset=True)

    if "telephony_provider_config_id" in updates and updates["telephony_provider_config_id"] is not None:
        get_provider(db, actor, updates["telephony_provider_config_id"])

    for field in _UPDATABLE_FIELDS:
        if field in updates and updates[field] is not None:
            setattr(config, field, updates[field])

    if "fields" in updates and updates["fields"] is not None:
        config.fields = updates["fields"]

    if "grant_user_ids" in updates and updates["grant_user_ids"] is not None and config.visibility == "restricted":
        db.query(CallAgentConfigGrant).filter(CallAgentConfigGrant.call_agent_config_id == config.id).delete()
        for user_id in updates["grant_user_ids"]:
            db.add(CallAgentConfigGrant(call_agent_config_id=config.id, user_id=user_id))

    db.commit()
    db.refresh(config)
    return config


def deactivate_call_agent(db: Session, actor: CurrentActor, config_id: uuid.UUID) -> CallAgentConfig:
    """Soft-delete: is_active=false. Never hard-deletes - historical Calls reference a snapshot
    of the script anyway, so this is safe and keeps their FK intact."""
    config = get_call_agent(db, actor, config_id)
    config.is_active = False
    db.commit()
    db.refresh(config)
    return config
