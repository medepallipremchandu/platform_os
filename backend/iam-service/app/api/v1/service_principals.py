import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentActor, get_db, require_permission
from app.schemas.service_principal import (
    RotateSecretResponse,
    ServicePrincipalCreatedResponse,
    ServicePrincipalCreateRequest,
    ServicePrincipalOut,
    ServicePrincipalPreviewOut,
)
from app.services import service_principal_service

router = APIRouter(prefix="/service-principals", tags=["service-principals"])


@router.post("", response_model=ServicePrincipalCreatedResponse, status_code=201)
def create_service_principal(
    payload: ServicePrincipalCreateRequest,
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(require_permission("talentos.iam.service_principals.manage")),
):
    sp, client_secret = service_principal_service.create_service_principal(
        db,
        organization_id=payload.organization_id,
        name=payload.name,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
    )
    return ServicePrincipalCreatedResponse(service_principal=sp, client_secret=client_secret)


@router.get("", response_model=list[ServicePrincipalPreviewOut])
def list_service_principals(
    organization_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(require_permission("talentos.iam.service_principals.manage")),
):
    return service_principal_service.list_service_principals(db, organization_id)


@router.post("/{service_principal_id}/secret/rotate", response_model=RotateSecretResponse)
def rotate_secret(
    service_principal_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(require_permission("talentos.iam.service_principals.manage")),
):
    client_secret = service_principal_service.rotate_secret(db, service_principal_id)
    return RotateSecretResponse(client_secret=client_secret)


@router.delete("/{service_principal_id}", status_code=204)
def revoke_service_principal(
    service_principal_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(require_permission("talentos.iam.service_principals.manage")),
):
    service_principal_service.revoke_service_principal(db, service_principal_id)
