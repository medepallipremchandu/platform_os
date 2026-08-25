import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import CurrentActor, get_db, require_permission
from app.core.constants import AuditResult
from app.schemas.role_assignment import RoleAssignmentCreateRequest, RoleAssignmentOut
from app.services import role_assignment_service
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/role-assignments", tags=["role-assignments"])


def _out(assignment) -> RoleAssignmentOut:
    return RoleAssignmentOut(
        id=assignment.id,
        principal_type=assignment.principal_type,
        principal_id=assignment.principal_id,
        role_definition_id=assignment.role_definition_id,
        role_definition_name=assignment.role_definition.name if assignment.role_definition else None,
        organization_id=assignment.organization_id,
        scope_type=assignment.scope_type,
        scope_id=assignment.scope_id,
        revoked_at=assignment.revoked_at,
        created_at=assignment.created_at,
    )


@router.post("", response_model=RoleAssignmentOut, status_code=201)
def create_role_assignment(
    payload: RoleAssignmentCreateRequest,
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(require_permission("talentos.iam.role_assignments.manage")),
):
    assignment = role_assignment_service.create_role_assignment(
        db,
        principal_type=payload.principal_type,
        principal_id=payload.principal_id,
        role_definition_id=payload.role_definition_id,
        organization_id=payload.organization_id,
        scope_type=payload.scope_type,
        service_name=payload.service_name,
    )
    return _out(assignment)


@router.get("", response_model=list[RoleAssignmentOut])
def list_role_assignments(
    organization_id: uuid.UUID = Query(...),
    include_revoked: bool = Query(default=False),
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(require_permission("talentos.iam.role_assignments.manage")),
):
    assignments = role_assignment_service.list_role_assignments(db, organization_id, include_revoked=include_revoked)
    return [_out(a) for a in assignments]


@router.delete("/{role_assignment_id}", status_code=204)
def revoke_role_assignment(
    role_assignment_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(require_permission("talentos.iam.role_assignments.manage")),
):
    """Soft delete: sets `revoked_at` rather than removing the row - see
    role_assignment_service.revoke_role_assignment and permission_service.resolve_permissions
    (which is what actually stops a revoked assignment's permissions from being granted)."""
    role_assignment_service.revoke_role_assignment(db, role_assignment_id)
    record_audit_event(
        db,
        organization_id=actor.org_id,
        actor_type=actor.principal_type,
        actor_id=actor.id,
        action="role_assignment.revoked",
        target_type="role_assignment",
        target_id=str(role_assignment_id),
        result=AuditResult.SUCCESS.value,
        source_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
