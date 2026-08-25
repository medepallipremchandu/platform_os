"""Permission resolution algorithm (design doc §5): the union of

  (a) permissions attached to any RoleDefinition the principal has via a RoleAssignment at
      "organization" scope for this org, and
  (b) permissions from any RoleAssignment at "service" scope where scope_id matches
      "<org_id>:<service_name>", for every known platform service.

Computed at token-issue time and embedded in the access token's `permissions` claim as a
flat, deduplicated list of permission code strings.

The resolved union is then intersected with the organization's entitlement ceiling
(`Organization.allowed_permissions`), if it has one. This function is the single enforcement
point for that ceiling, and it is enough on its own precisely because it runs on EVERY token
issuance: a role granting a permission outside the ceiling simply never appears on any token,
regardless of how that role was authored or assigned, and revoking an entitlement takes effect
on the very next token rather than requiring any role to be rewritten.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import ServiceName, build_service_scope_id
from app.models.organization import Organization
from app.models.permission import Permission
from app.models.role_assignment import RoleAssignment
from app.models.role_definition import RoleDefinition
from app.models.role_definition_permission import RoleDefinitionPermission


def organization_ceiling(db: Session, organization_id: uuid.UUID) -> set[str] | None:
    """The organization's allowed permission codes, or None for "unrestricted".

    None and an empty list mean the same thing on purpose - unrestricted - so an organization
    created before entitlements existed (NULL) and one whose ceiling was cleared behave
    identically, and neither is accidentally locked out of everything."""
    org = db.get(Organization, organization_id)
    if org is None or not org.allowed_permissions:
        return None
    return set(org.allowed_permissions)


def resolve_permissions(db: Session, *, principal_type: str, principal_id: uuid.UUID, organization_id: uuid.UUID) -> list[str]:
    org_scope_id = str(organization_id)
    service_scope_ids = [build_service_scope_id(organization_id, s.value) for s in ServiceName]

    # revoked_at IS NULL and archived_at IS NULL are both load-bearing: a revoked RoleAssignment
    # or an archived RoleDefinition must stop contributing permissions on the very next token
    # issuance, not just disappear from list views (see role_assignment_service.py /
    # role_definition_service.py docstrings for the soft-delete convention this enforces).
    stmt = (
        select(RoleAssignment.role_definition_id)
        .join(RoleDefinition, RoleDefinition.id == RoleAssignment.role_definition_id)
        .where(
            RoleAssignment.principal_type == principal_type,
            RoleAssignment.principal_id == principal_id,
            RoleAssignment.organization_id == organization_id,
            RoleAssignment.revoked_at.is_(None),
            RoleDefinition.archived_at.is_(None),
            (
                ((RoleAssignment.scope_type == "organization") & (RoleAssignment.scope_id == org_scope_id))
                | ((RoleAssignment.scope_type == "service") & (RoleAssignment.scope_id.in_(service_scope_ids)))
            ),
        )
    )
    role_definition_ids = list(db.execute(stmt).scalars().all())
    if not role_definition_ids:
        return []

    ceiling = organization_ceiling(db, organization_id)

    perm_stmt = (
        select(Permission.code)
        .join(RoleDefinitionPermission, RoleDefinitionPermission.permission_id == Permission.id)
        .where(RoleDefinitionPermission.role_definition_id.in_(role_definition_ids))
        .distinct()
    )
    codes = list(db.execute(perm_stmt).scalars().all())
    if ceiling is not None:
        codes = [code for code in codes if code in ceiling]
    return codes
