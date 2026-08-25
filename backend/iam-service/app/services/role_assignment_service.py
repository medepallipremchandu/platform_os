import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.constants import ServiceName, build_service_scope_id
from app.core.exceptions import InvalidStateError, NotFoundError
from app.models.role_assignment import RoleAssignment
from app.models.role_definition import RoleDefinition


def create_role_assignment(
    db: Session,
    *,
    principal_type: str,
    principal_id: uuid.UUID,
    role_definition_id: uuid.UUID,
    organization_id: uuid.UUID,
    scope_type: str,
    service_name: str | None,
) -> RoleAssignment:
    role = db.get(RoleDefinition, role_definition_id)
    if role is None:
        raise NotFoundError("Role definition not found")
    if role.archived_at is not None:
        raise InvalidStateError("Cannot assign an archived role definition")

    if scope_type == "organization":
        scope_id = str(organization_id)
    else:
        valid_names = {s.value for s in ServiceName}
        if service_name not in valid_names:
            raise InvalidStateError(f"service_name must be one of {sorted(valid_names)}")
        scope_id = build_service_scope_id(organization_id, service_name)

    assignment = RoleAssignment(
        principal_type=principal_type,
        principal_id=principal_id,
        role_definition_id=role_definition_id,
        organization_id=organization_id,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def list_role_assignments(
    db: Session, organization_id: uuid.UUID, *, include_revoked: bool = False
) -> list[RoleAssignment]:
    stmt = (
        select(RoleAssignment)
        .options(selectinload(RoleAssignment.role_definition))
        .where(RoleAssignment.organization_id == organization_id)
        .order_by(RoleAssignment.created_at.desc())
    )
    if not include_revoked:
        stmt = stmt.where(RoleAssignment.revoked_at.is_(None))
    return list(db.execute(stmt).scalars().all())


def revoke_role_assignment(db: Session, role_assignment_id: uuid.UUID) -> RoleAssignment:
    """Soft delete: sets `revoked_at` instead of removing the row. Critical - this is only half
    the fix. The other half is permission_service.resolve_permissions filtering
    `revoked_at IS NULL`, or a revoked assignment keeps silently granting its permissions on
    every future token issuance."""
    assignment = db.get(RoleAssignment, role_assignment_id)
    if assignment is None:
        raise NotFoundError("Role assignment not found")
    if assignment.revoked_at is None:
        assignment.revoked_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(assignment)
    return assignment
