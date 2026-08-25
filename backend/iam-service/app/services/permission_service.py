"""Permission resolution algorithm (design doc §5): the union of

  (a) permissions attached to any RoleDefinition the principal has via a RoleAssignment at
      "organization" scope for this org, and
  (b) permissions from any RoleAssignment at "service" scope where scope_id matches
      "<org_id>:<service_name>", for every known platform service.

Computed at token-issue time and embedded in the access token's `permissions` claim as a
flat, deduplicated list of permission code strings.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import ServiceName, build_service_scope_id
from app.models.permission import Permission
from app.models.role_assignment import RoleAssignment
from app.models.role_definition_permission import RoleDefinitionPermission


def resolve_permissions(db: Session, *, principal_type: str, principal_id: uuid.UUID, organization_id: uuid.UUID) -> list[str]:
    org_scope_id = str(organization_id)
    service_scope_ids = [build_service_scope_id(organization_id, s.value) for s in ServiceName]

    stmt = select(RoleAssignment.role_definition_id).where(
        RoleAssignment.principal_type == principal_type,
        RoleAssignment.principal_id == principal_id,
        RoleAssignment.organization_id == organization_id,
        (
            ((RoleAssignment.scope_type == "organization") & (RoleAssignment.scope_id == org_scope_id))
            | ((RoleAssignment.scope_type == "service") & (RoleAssignment.scope_id.in_(service_scope_ids)))
        ),
    )
    role_definition_ids = list(db.execute(stmt).scalars().all())
    if not role_definition_ids:
        return []

    perm_stmt = (
        select(Permission.code)
        .join(RoleDefinitionPermission, RoleDefinitionPermission.permission_id == Permission.id)
        .where(RoleDefinitionPermission.role_definition_id.in_(role_definition_ids))
        .distinct()
    )
    return list(db.execute(perm_stmt).scalars().all())
