import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.models.organization import Organization
from app.models.organization_membership import OrganizationMembership


def create_organization(db: Session, *, name: str) -> Organization:
    existing = db.execute(select(Organization).where(Organization.name == name)).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"Organization '{name}' already exists")
    org = Organization(name=name)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def list_organizations_for_user(db: Session, user_id: uuid.UUID) -> list[Organization]:
    stmt = (
        select(Organization)
        .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
        .where(OrganizationMembership.user_id == user_id, OrganizationMembership.status == "active")
    )
    return list(db.execute(stmt).scalars().all())
