"""The provider-configuration API.

Everything here is organization-scoped and authorized by app.core_iam.require_org_permission,
which means a superadmin can administer any tenant while an organization admin can only ever
reach their own - see that dependency's docstring for why the org check is not optional even
for a caller holding the permission.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core_crypto import SecretsUnavailableError, decrypt_secrets
from app.core_iam import CurrentActor, require_org_permission
from app.database import get_db
from app.models import EmailLog, NotificationProviderConfig
from app.providers.base import ProviderConfigError
from app.providers.registry import catalog, provider_class
from app.schemas import (
    EmailLogOut,
    EmailLogPage,
    ProviderConfigCreate,
    ProviderConfigOut,
    ProviderConfigUpdate,
    ProviderSpecOut,
    ProviderTestResult,
    ResolvedProvidersOut,
)
from app.services import provider_config_service, resolver

PROVIDERS_READ = "talentos.notifications.providers.read"
PROVIDERS_MANAGE = "talentos.notifications.providers.manage"
LOGS_READ = "talentos.notifications.logs.read"

router = APIRouter(tags=["notification-providers"])


@router.get("/providers/catalog", response_model=list[ProviderSpecOut])
def provider_catalog():
    """The registry itself: every provider, its fields, and which of them are secret. This is
    what lets iam-console render a config form for a provider it has never heard of - adding a
    provider on the backend needs no frontend change."""
    return catalog()


def _to_out(row: NotificationProviderConfig) -> ProviderConfigOut:
    try:
        secrets_set = sorted(decrypt_secrets(row.secrets_encrypted))
    except SecretsUnavailableError:
        # The key is missing or has changed. Listing must still work - an operator needs to see
        # the row in order to fix it - so report "no secrets readable" rather than 500.
        secrets_set = []
    declared_secrets = provider_class(row.kind, row.provider).secret_field_names()
    out = ProviderConfigOut.model_validate(row)
    out.secrets_set = [name for name in secrets_set if name in declared_secrets]
    return out


@router.get("/organizations/{organization_id}/notification-providers", response_model=list[ProviderConfigOut])
def list_providers(
    organization_id: uuid.UUID,
    kind: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(require_org_permission(PROVIDERS_READ, PROVIDERS_MANAGE)),
):
    rows = provider_config_service.list_configs(db, organization_id, kind=kind, include_archived=include_archived)
    return [_to_out(row) for row in rows]


@router.get("/organizations/{organization_id}/notification-providers/resolved", response_model=ResolvedProvidersOut)
def resolved_providers(
    organization_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(require_org_permission(PROVIDERS_READ, PROVIDERS_MANAGE)),
):
    email = resolver.resolve_email_provider(db, organization_id)
    queue = resolver.resolve_queue_provider(db, organization_id)
    return ResolvedProvidersOut(
        email_provider=email.key,
        email_scope=email.scope,
        queue_provider=queue.key if queue else "platform-default",
        queue_scope=queue.scope if queue else resolver.SCOPE_PLATFORM,
    )


@router.post(
    "/organizations/{organization_id}/notification-providers",
    response_model=ProviderConfigOut,
    status_code=status.HTTP_201_CREATED,
)
def create_provider(
    organization_id: uuid.UUID,
    payload: ProviderConfigCreate,
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(require_org_permission(PROVIDERS_MANAGE)),
):
    try:
        row = provider_config_service.create_config(
            db,
            organization_id,
            kind=payload.kind,
            provider=payload.provider,
            name=payload.name,
            config=payload.config,
            is_enabled=payload.is_enabled,
        )
    except ProviderConfigError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except SecretsUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except IntegrityError:
        # uq_notification_provider_enabled_per_kind, hit by a genuinely concurrent write: the
        # service layer disables siblings first, so reaching here means another request enabled
        # one in between. A conflict, not a fault.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another provider of this kind was enabled concurrently - reload and try again.",
        )
    return _to_out(row)


@router.patch(
    "/organizations/{organization_id}/notification-providers/{config_id}", response_model=ProviderConfigOut
)
def update_provider(
    organization_id: uuid.UUID,
    config_id: uuid.UUID,
    payload: ProviderConfigUpdate,
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(require_org_permission(PROVIDERS_MANAGE)),
):
    try:
        row = provider_config_service.update_config(
            db,
            organization_id,
            config_id,
            name=payload.name,
            config=payload.config,
            is_enabled=payload.is_enabled,
        )
    except provider_config_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ProviderConfigError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except SecretsUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return _to_out(row)


@router.delete(
    "/organizations/{organization_id}/notification-providers/{config_id}", response_model=ProviderConfigOut
)
def archive_provider(
    organization_id: uuid.UUID,
    config_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(require_org_permission(PROVIDERS_MANAGE)),
):
    """Soft delete - the row is archived and disabled, never removed, matching the platform-wide
    convention. Named DELETE because that is what the console's affordance means; the response
    body shows the archived row so the caller can see what actually happened."""
    try:
        return _to_out(provider_config_service.archive_config(db, organization_id, config_id))
    except provider_config_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/organizations/{organization_id}/notification-providers/{config_id}/test", response_model=ProviderTestResult
)
def test_provider(
    organization_id: uuid.UUID,
    config_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(require_org_permission(PROVIDERS_MANAGE)),
):
    try:
        ok, message = provider_config_service.test_config(db, organization_id, config_id)
    except provider_config_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return ProviderTestResult(ok=ok, message=message)


@router.get("/organizations/{organization_id}/email-logs", response_model=EmailLogPage)
def list_email_logs(
    organization_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(require_org_permission(LOGS_READ, PROVIDERS_MANAGE)),
):
    where = EmailLog.organization_id == organization_id
    total = db.execute(select(func.count()).select_from(EmailLog).where(where)).scalar_one()
    rows = (
        db.execute(
            select(EmailLog).where(where).order_by(EmailLog.created_at.desc()).limit(limit).offset(offset)
        )
        .scalars()
        .all()
    )
    return EmailLogPage(
        items=[EmailLogOut.model_validate(row) for row in rows], total=total, limit=limit, offset=offset
    )
