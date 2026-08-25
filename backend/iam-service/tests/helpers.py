import uuid

from sqlalchemy import select

from app.core.constants import ServiceName, build_service_scope_id
from app.core.password import hash_password
from app.models.organization import Organization
from app.models.organization_membership import OrganizationMembership
from app.models.role_assignment import RoleAssignment
from app.models.role_definition import RoleDefinition
from app.models.user import User


def create_org(db, name: str | None = None) -> Organization:
    org = Organization(name=name or f"Org-{uuid.uuid4().hex[:8]}")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def create_user(db, email: str, password: str = "correct-horse-battery", status: str = "active") -> User:
    user = User(email=email, password_hash=hash_password(password), status=status, display_name="Test User")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def add_membership(db, user: User, org: Organization, status: str = "active") -> OrganizationMembership:
    m = OrganizationMembership(user_id=user.id, organization_id=org.id, status=status)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def get_builtin_role(db, name: str) -> RoleDefinition:
    return db.execute(
        select(RoleDefinition).where(RoleDefinition.organization_id.is_(None), RoleDefinition.name == name)
    ).scalar_one()


def assign_org_role(db, *, principal_type: str, principal_id, role_definition_id, organization_id) -> RoleAssignment:
    ra = RoleAssignment(
        principal_type=principal_type,
        principal_id=principal_id,
        role_definition_id=role_definition_id,
        organization_id=organization_id,
        scope_type="organization",
        scope_id=str(organization_id),
    )
    db.add(ra)
    db.commit()
    db.refresh(ra)
    return ra


def assign_service_role(db, *, principal_type: str, principal_id, role_definition_id, organization_id, service_name: ServiceName) -> RoleAssignment:
    ra = RoleAssignment(
        principal_type=principal_type,
        principal_id=principal_id,
        role_definition_id=role_definition_id,
        organization_id=organization_id,
        scope_type="service",
        scope_id=build_service_scope_id(organization_id, service_name.value),
    )
    db.add(ra)
    db.commit()
    db.refresh(ra)
    return ra
