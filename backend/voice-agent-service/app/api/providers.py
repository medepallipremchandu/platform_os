from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import CurrentActor, get_db, require_permission
from app.core.iam_client import post_audit_event
from app.core.permissions import PROVIDERS_MANAGE, PROVIDERS_READ
from app.schemas.providers import (
    TelephonyProviderCreateRequest,
    TelephonyProviderListResponse,
    TelephonyProviderResponse,
    TelephonyProviderUpdateRequest,
)
from app.services import providers_service

router = APIRouter(prefix="/providers", tags=["providers"])


def _to_response(config) -> TelephonyProviderResponse:
    return TelephonyProviderResponse(
        id=config.id,
        organization_id=config.organization_id,
        name=config.name,
        provider=config.provider,
        phone_number=config.phone_number,
        visibility=config.visibility,
        created_by=config.created_by,
        created_at=config.created_at,
        revoked_at=config.revoked_at,
    )


@router.post("", response_model=TelephonyProviderResponse, status_code=201)
async def create_provider(
    payload: TelephonyProviderCreateRequest,
    actor: CurrentActor = Depends(require_permission(PROVIDERS_MANAGE)),
    db: Session = Depends(get_db),
):
    config = providers_service.create_provider(db, actor, payload)
    await post_audit_event(
        actor.token, action="voiceagent.provider.create", target_type="TelephonyProviderConfig", target_id=str(config.id)
    )
    return _to_response(config)


@router.get("", response_model=TelephonyProviderListResponse)
async def list_providers(
    include_revoked: bool = False,
    actor: CurrentActor = Depends(require_permission(PROVIDERS_READ)),
    db: Session = Depends(get_db),
):
    configs = providers_service.list_providers(db, actor, include_revoked)
    return TelephonyProviderListResponse(items=[_to_response(c) for c in configs])


@router.patch("/{provider_id}", response_model=TelephonyProviderResponse)
async def update_provider(
    provider_id: uuid.UUID,
    payload: TelephonyProviderUpdateRequest,
    actor: CurrentActor = Depends(require_permission(PROVIDERS_MANAGE)),
    db: Session = Depends(get_db),
):
    config = providers_service.update_provider(db, actor, provider_id, payload)
    await post_audit_event(
        actor.token, action="voiceagent.provider.update", target_type="TelephonyProviderConfig", target_id=str(config.id)
    )
    return _to_response(config)


@router.delete("/{provider_id}", response_model=TelephonyProviderResponse)
async def revoke_provider(
    provider_id: uuid.UUID,
    actor: CurrentActor = Depends(require_permission(PROVIDERS_MANAGE)),
    db: Session = Depends(get_db),
):
    config = providers_service.revoke_provider(db, actor, provider_id)
    await post_audit_event(
        actor.token, action="voiceagent.provider.revoke", target_type="TelephonyProviderConfig", target_id=str(config.id)
    )
    return _to_response(config)
