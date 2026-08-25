"""Emailed-token password reset - and, deliberately, invite activation too.

There is exactly ONE token type and ONE confirm endpoint for both flows. An invited user
setting their first password and an existing user who forgot theirs are the same operation from
the system's point of view: prove possession of an emailed single-use token, then set a
password. Building a parallel "activation token" table and an /auth/activate endpoint would
have doubled the security-sensitive surface to express a distinction that does not exist -
so `confirm_password_reset` simply also flips a status="invited" user to "active".

Tokens are stored only as a hash and are single-use (used_at set on redemption). Delivery goes
through notification_client, which publishes to notification-service and never lets a
queue-publish failure break the caller.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.password import hash_password
from app.core.secrets import generate_reset_token, hash_secret
from app.models.organization_membership import OrganizationMembership
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.services import notification_client

logger = logging.getLogger("app.password_reset")


def issue_reset_token(db: Session, settings: Settings, user: User) -> str:
    """Mint and persist a single-use token, returning the plaintext for the caller to email.

    Split out from `request_password_reset` because the invite flows need the same token but a
    different email template - one token mechanism, several messages wrapped around it."""
    plain = generate_reset_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_secret(plain),
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        )
    )
    db.commit()
    return plain


def _primary_organization_id(db: Session, user_id: uuid.UUID) -> uuid.UUID | None:
    """Which organization's email provider should send this user's reset. A user in several
    organizations gets whichever membership is oldest; a platform superadmin has none, and gets
    the platform default. Either way this only selects a PROVIDER - it grants nothing."""
    return db.execute(
        select(OrganizationMembership.organization_id)
        .where(OrganizationMembership.user_id == user_id, OrganizationMembership.status == "active")
        .order_by(OrganizationMembership.created_at)
        .limit(1)
    ).scalar_one_or_none()


def request_password_reset(db: Session, settings: Settings, *, email: str) -> None:
    email_norm = email.strip().lower()
    user = db.execute(select(User).where(User.email == email_norm)).scalar_one_or_none()
    if user is None:
        # Do not reveal whether the email exists - the endpoint answers 202 either way.
        logger.info("Password reset requested for unknown email %s - no-op", email_norm)
        return

    plain = issue_reset_token(db, settings, user)
    notification_client.send_password_reset(
        settings,
        to_email=email_norm,
        display_name=user.display_name,
        token=plain,
        organization_id=_primary_organization_id(db, user.id),
    )


def confirm_password_reset(db: Session, settings: Settings, *, token: str, new_password: str) -> None:
    from app.core.exceptions import InvalidStateError

    if len(new_password) < settings.PASSWORD_MIN_LENGTH:
        raise InvalidStateError(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters")

    token_hash = hash_secret(token)
    row = db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if row is None or row.used_at is not None:
        raise InvalidStateError("Invalid or already-used reset token")

    expires_at = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise InvalidStateError("Reset token has expired")

    user = db.get(User, row.user_id)
    if user is None:
        raise InvalidStateError("Invalid reset token")

    user.password_hash = hash_password(new_password)
    # This one line is the whole of "first-login set password": an invited user redeeming their
    # invite token becomes active. No separate activation endpoint, no second token type.
    if user.status == "invited":
        user.status = "active"
    row.used_at = now
    db.commit()
