import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import CurrentActor, current_actor, get_db, require_permission
from app.core.constants import AuditResult
from app.schemas.role_definition import RoleDefinitionCreateRequest, RoleDefinitionOut, RoleDefinitionUpdateRequest
from app.services import role_definition_service
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/role-definitions", tags=["role-definitions"])


@router.get("", response_model=list[RoleDefinitionOut])
def list_role_definitions(
    organization_id: uuid.UUID = Query(...),
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(current_actor),
):
    return role_definition_service.list_role_definitions(db, organization_id, include_archived=include_archived)


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
def archive_role_definition(
    role_definition_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(require_permission("talentos.iam.roles.manage")),
):
    """Soft delete: archives the custom role (sets `archived_at`) rather than removing the row -
    see role_definition_service.archive_role_definition."""
    role_definition_service.archive_role_definition(db, role_definition_id)
    record_audit_event(
        db,
        organization_id=actor.org_id,
        actor_type=actor.principal_type,
        actor_id=actor.id,
        action="role_definition.archived",
        target_type="role_definition",
        target_id=str(role_definition_id),
        result=AuditResult.SUCCESS.value,
        source_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
