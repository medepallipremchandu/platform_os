import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentActor, current_actor, get_db, require_permission
from app.schemas.role_definition import RoleDefinitionCreateRequest, RoleDefinitionOut, RoleDefinitionUpdateRequest
from app.services import role_definition_service

router = APIRouter(prefix="/role-definitions", tags=["role-definitions"])


@router.get("", response_model=list[RoleDefinitionOut])
def list_role_definitions(
    organization_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(current_actor),
):
    return role_definition_service.list_role_definitions(db, organization_id)


@router.post("", response_model=RoleDefinitionOut, status_code=201)
def create_role_definition(
    payload: RoleDefinitionCreateRequest,
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(require_permission("talentos.iam.roles.manage")),
):
    return role_definition_service.create_role_definition(
        db,
        organization_id=payload.organization_id,
        name=payload.name,
        description=payload.description,
        permission_codes=payload.permission_codes,
    )


@router.patch("/{role_definition_id}", response_model=RoleDefinitionOut)
def update_role_definition(
    role_definition_id: uuid.UUID,
    payload: RoleDefinitionUpdateRequest,
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(require_permission("talentos.iam.roles.manage")),
):
    return role_definition_service.update_role_definition(
        db,
        role_definition_id,
        name=payload.name,
        description=payload.description,
        permission_codes=payload.permission_codes,
    )


@router.delete("/{role_definition_id}", status_code=204)
def delete_role_definition(
    role_definition_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(require_permission("talentos.iam.roles.manage")),
):
    role_definition_service.delete_role_definition(db, role_definition_id)
