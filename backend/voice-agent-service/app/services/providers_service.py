from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_credentials
from app.core.exceptions import NotFoundError
from app.core.iam_client import CurrentActor
from app.models.telephony_provider import TelephonyProviderConfig, TelephonyProviderConfigGrant
from app.schemas.providers import TelephonyProviderCreateRequest, TelephonyProviderUpdateRequest
from app.services.visibility import visible_query


def create_provider(db: Session, actor: CurrentActor, payload: TelephonyProviderCreateRequest) -> TelephonyProviderConfig:
    config = TelephonyProviderConfig(
        organization_id=uuid.UUID(actor.org_id),
        name=payload.name,
        provider=payload.provider,
        phone_number=payload.phone_number,
        encrypted_credentials=encrypt_credentials(payload.credentials),
        visibility=payload.visibility,
        created_by=actor.email_or_name,
    )
    db.add(config)
    db.flush()

    if payload.visibility == "restricted":
        for user_id in payload.grant_user_ids:
            db.add(TelephonyProviderConfigGrant(provider_config_id=config.id, user_id=user_id))

    db.commit()
    db.refresh(config)
    return config


def list_providers(db: Session, actor: CurrentActor, include_revoked: bool = False) -> list[TelephonyProviderConfig]:
    query = visible_query(
        db, TelephonyProviderConfig, TelephonyProviderConfigGrant, TelephonyProviderConfigGrant.provider_config_id, actor
    )
    if not include_revoked:
        query = query.where(TelephonyProviderConfig.revoked_at.is_(None))
    return list(db.execute(query.order_by(TelephonyProviderConfig.created_at.desc())).scalars().all())


def get_provider(db: Session, actor: CurrentActor, provider_id: uuid.UUID) -> TelephonyProviderConfig:
    query = visible_query(
        db, TelephonyProviderConfig, TelephonyProviderConfigGrant, TelephonyProviderConfigGrant.provider_config_id, actor
    ).where(TelephonyProviderConfig.id == provider_id)
    config = db.execute(query).scalar_one_or_none()
    if config is None:
        raise NotFoundError("Telephony provider config not found")
    return config


def get_provider_for_call(db: Session, organization_id: uuid.UUID, provider_id: uuid.UUID) -> TelephonyProviderConfig:
    """Org-scoped only (no visibility filtering) - used internally by call placement/webhooks,
    which act on the org's behalf regardless of which human created/restricted the config."""
    result = db.execute(
        select(TelephonyProviderConfig).where(
            TelephonyProviderConfig.id == provider_id, TelephonyProviderConfig.organization_id == organization_id
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise NotFoundError("Telephony provider config not found")
    return config


def update_provider(
    db: Session, actor: CurrentActor, provider_id: uuid.UUID, payload: TelephonyProviderUpdateRequest
) -> TelephonyProviderConfig:
    config = get_provider(db, actor, provider_id)
    updates = payload.model_dump(exclude_unset=True)

    if "name" in updates and updates["name"] is not None:
        config.name = updates["name"]
    if "phone_number" in updates and updates["phone_number"] is not None:
        config.phone_number = updates["phone_number"]
    if "credentials" in updates and updates["credentials"] is not None:
        config.encrypted_credentials = encrypt_credentials(updates["credentials"])

    db.commit()
    db.refresh(config)
    return config


def revoke_provider(db: Session, actor: CurrentActor, provider_id: uuid.UUID) -> TelephonyProviderConfig:
    config = get_provider(db, actor, provider_id)
    config.revoked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(config)
    return config
