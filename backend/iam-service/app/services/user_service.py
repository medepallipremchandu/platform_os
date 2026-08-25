import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from app.services.password_reset_service import request_password_reset


def invite_user(db, settings, *, organization_id: uuid.UUID, email: str, display_name: str | None) -> User:
    email_norm = email.strip().lower()
    user = db.execute(select(User).where(User.email == email_norm)).scalar_one_or_none()
    if user is None:
        user = User(email=email_norm, display_name=display_name, status="invited")
        db.add(user)
        db.flush()

    membership = db.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == organization_id,
        )
    ).scalar_one_or_none()
    if membership is None:
        membership = OrganizationMembership(user_id=user.id, organization_id=organization_id, status="active")
        db.add(membership)
    db.commit()
    db.refresh(user)

    # Let the invitee set their own password via the same reset flow (email delivery stubbed
    # to a log line, per design doc §1 non-goals).
    request_password_reset(db, settings, email=email_norm)
    return user


def list_organization_members(db: Session, organization_id: uuid.UUID) -> list[OrganizationMembership]:
    stmt = (
        select(OrganizationMembership)
        .where(OrganizationMembership.organization_id == organization_id)
        .join(User, User.id == OrganizationMembership.user_id)
    )
    return list(db.execute(stmt).scalars().all())


def update_membership_status(db: Session, organization_id: uuid.UUID, user_id: uuid.UUID, status: str) -> OrganizationMembership:
    membership = db.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
    ).scalar_one_or_none()
    if membership is None:
        raise NotFoundError("Membership not found")
    membership.status = status
    db.commit()
    db.refresh(membership)
    return membership
