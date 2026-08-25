import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.organization import Organization
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from app.services import notification_client
from app.services.password_reset_service import issue_reset_token


def invite_user(
    db,
    settings,
    *,
    organization_id: uuid.UUID,
    email: str,
    display_name: str | None,
    is_org_admin: bool = False,
) -> User:
    """Create (or reuse) a user, put them in the organization, and email them a set-password
    link.

    The invitee has no usable password - status "invited", password_hash NULL - and becomes
    "active" only by redeeming the emailed token (see password_reset_service:
    confirm_password_reset). An existing user invited into a second organization keeps the
    password and status they already have; only the membership is new.

    `is_org_admin` selects the email template, nothing else. The role assignment that actually
    makes someone an admin is a separate, explicit step - see
    organization_service.create_organization_with_admin."""
    email_norm = email.strip().lower()
    user = db.execute(select(User).where(User.email == email_norm)).scalar_one_or_none()
    is_new_user = user is None
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

    organization = db.get(Organization, organization_id)
    if is_new_user or user.status == "invited":
        token = issue_reset_token(db, settings, user)
        notification_client.send_invite(
            settings,
            to_email=email_norm,
            display_name=user.display_name,
            organization_name=organization.name if organization else "TalentOS",
            organization_id=organization_id,
            token=token,
            is_org_admin=is_org_admin,
        )
    else:
        # An already-active user added to another organization does not need - and must not be
        # handed - a password-reset token they did not ask for. Minting one on every invite
        # would turn "add an existing colleague to my org" into an unsolicited credential reset.
        notification_client.send_email(
            settings,
            to_email=email_norm,
            template=notification_client.TEMPLATE_USER_INVITE,
            context={
                "organization_name": organization.name if organization else "TalentOS",
                "display_name": user.display_name or email_norm,
                "set_password_url": f"{settings.PORTAL_URL.rstrip('/')}/login",
            },
            organization_id=organization_id,
        )
    return user


def list_organization_members(db: Session, organization_id: uuid.UUID) -> list[OrganizationMembership]:
    stmt = (
        select(OrganizationMembership)
        .where(OrganizationMembership.organization_id == organization_id)
        .join(User, User.id == OrganizationMembership.user_id)
    )
    return list(db.execute(stmt).scalars().all())


def update_membership(
    db: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    status: str | None = None,
    display_name: str | None = None,
) -> OrganizationMembership:
    """`status` toggles the membership row (active/disabled); `display_name` edits the
    underlying User row (shared across every org that user belongs to, same as email)."""
    membership = db.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
    ).scalar_one_or_none()
    if membership is None:
        raise NotFoundError("Membership not found")
    if status is not None:
        membership.status = status
    if display_name is not None:
        user = db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found")
        user.display_name = display_name
    db.commit()
    db.refresh(membership)
    return membership
