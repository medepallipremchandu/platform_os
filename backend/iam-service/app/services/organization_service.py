import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, InvalidStateError, NotFoundError
from app.models.organization import Organization
from app.models.organization_membership import OrganizationMembership
from app.models.permission import Permission
from app.models.role_assignment import RoleAssignment
from app.models.role_definition import RoleDefinition

ORG_ADMIN_ROLE_NAME = "Organization Admin"


def create_organization(db: Session, *, name: str, allowed_permissions: list[str] | None = None) -> Organization:
    existing = db.execute(select(Organization).where(Organization.name == name)).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"Organization '{name}' already exists")
    org = Organization(name=name, allowed_permissions=allowed_permissions or None)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def validate_permission_codes(db: Session, codes: list[str]) -> list[str]:
    """Reject unknown codes rather than storing them. A typo in a ceiling is silently
    restrictive - the permission it was meant to allow just never appears on a token - which is
    exactly the kind of failure that is impossible to diagnose from the outside."""
    known = set(db.execute(select(Permission.code)).scalars().all())
    unknown = sorted(set(codes) - known)
    if unknown:
        raise InvalidStateError(f"Unknown permission code(s): {', '.join(unknown)}")
    return sorted(set(codes))


def set_entitlements(db: Session, organization_id: uuid.UUID, *, allowed_permission_codes: list[str]) -> Organization:
    """Set (or clear, with an empty list) this organization's permission ceiling.

    Takes effect on the next token issued to any of its members - there is nothing to
    re-synchronize, because the ceiling is applied at resolution time rather than baked into
    roles. See permission_service.resolve_permissions."""
    org = _get_or_404(db, organization_id)
    org.allowed_permissions = validate_permission_codes(db, allowed_permission_codes) or None
    org.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(org)
    return org


def create_organization_with_admin(
    db: Session,
    settings,
    *,
    name: str,
    admin_email: str,
    admin_display_name: str | None,
    allowed_permission_codes: list[str],
) -> tuple[Organization, "User"]:  # noqa: F821
    """The superadmin's one-shot tenant provisioning: organization + its ceiling + its first
    admin + that admin's role assignment + the invite email, in one transaction.

    Requiring at least one permission code is deliberate. An organization created with an empty
    ceiling would be one whose members can hold no permissions at all - a tenant that exists but
    cannot be used - and silently creating that is worse than refusing. Granting has to be an
    explicit act.

    The organization and the membership commit together: a half-provisioned tenant (an
    organization with no admin, or an admin with no role) is not a state anyone should have to
    reason about. The invite email is sent AFTER the commit, and cannot fail the operation - see
    notification_client.
    """
    from app.services import user_service

    codes = validate_permission_codes(db, allowed_permission_codes)
    if not codes:
        raise InvalidStateError(
            "At least one permission code is required - an organization with an empty "
            "entitlement ceiling could grant nothing to anyone."
        )

    existing = db.execute(select(Organization).where(Organization.name == name)).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"Organization '{name}' already exists")

    admin_role = db.execute(
        select(RoleDefinition).where(
            RoleDefinition.organization_id.is_(None),
            RoleDefinition.name == ORG_ADMIN_ROLE_NAME,
            RoleDefinition.is_builtin.is_(True),
        )
    ).scalar_one_or_none()
    if admin_role is None:
        raise InvalidStateError(
            f"Built-in '{ORG_ADMIN_ROLE_NAME}' role is missing - run scripts/seed_permissions_and_roles.py"
        )

    org = Organization(name=name, allowed_permissions=codes)
    db.add(org)
    db.flush()

    # invite_user commits (it has to, so the token row references a persisted user), which is
    # why the organization is flushed above rather than committed separately - both land in the
    # same transaction.
    admin = user_service.invite_user(
        db,
        settings,
        organization_id=org.id,
        email=admin_email,
        display_name=admin_display_name,
        is_org_admin=True,
    )

    already_assigned = db.execute(
        select(RoleAssignment).where(
            RoleAssignment.principal_type == "user",
            RoleAssignment.principal_id == admin.id,
            RoleAssignment.role_definition_id == admin_role.id,
            RoleAssignment.organization_id == org.id,
            RoleAssignment.revoked_at.is_(None),
        )
    ).scalar_one_or_none()
    if already_assigned is None:
        db.add(
            RoleAssignment(
                principal_type="user",
                principal_id=admin.id,
                role_definition_id=admin_role.id,
                organization_id=org.id,
                scope_type="organization",
                scope_id=str(org.id),
            )
        )
    db.commit()
    db.refresh(org)
    db.refresh(admin)
    return org, admin


def list_all_organizations(db: Session) -> list[Organization]:
    """Every organization platform-wide. Superadmin-only at the API layer - an org-scoped
    principal must never enumerate other tenants."""
    return list(db.execute(select(Organization).order_by(Organization.name)).scalars().all())


def list_organizations_for_user(db: Session, user_id: uuid.UUID) -> list[Organization]:
    stmt = (
        select(Organization)
        .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
        .where(OrganizationMembership.user_id == user_id, OrganizationMembership.status == "active")
    )
    return list(db.execute(stmt).scalars().all())


def _get_or_404(db: Session, organization_id: uuid.UUID) -> Organization:
    org = db.get(Organization, organization_id)
    if org is None:
        raise NotFoundError("Organization not found")
    return org


def rename_organization(db: Session, organization_id: uuid.UUID, *, name: str) -> Organization:
    org = _get_or_404(db, organization_id)
    existing = db.execute(
        select(Organization).where(Organization.name == name, Organization.id != organization_id)
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"Organization '{name}' already exists")
    org.name = name
    org.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(org)
    return org


def deactivate_organization(db: Session, organization_id: uuid.UUID) -> Organization:
    """Soft delete for a tenant root: never removes the row. A deactivated org's users are
    rejected at login (see auth_service.login) - the org and everything under it (users, roles,
    role assignments, service principals) is preserved for audit/history and can be restored via
    reactivate_organization."""
    org = _get_or_404(db, organization_id)
    if org.is_active:
        org.is_active = False
        org.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(org)
    return org


def reactivate_organization(db: Session, organization_id: uuid.UUID) -> Organization:
    org = _get_or_404(db, organization_id)
    if not org.is_active:
        org.is_active = True
        org.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(org)
    return org
