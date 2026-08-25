"""Emailed-token password reset flow (design doc §4.1 / §1 non-goals). Email delivery is a
stub: the reset link/token is logged at INFO level instead of actually sent, matching this
codebase's existing local-dev posture for anything email-shaped (see agent-builder-service /
talentos-app, which take the same approach for anything outbound they don't
actually wire up yet)."""
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.password import hash_password
from app.core.secrets import generate_reset_token, hash_secret
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User

logger = logging.getLogger("app.password_reset")


def request_password_reset(db: Session, settings: Settings, *, email: str) -> None:
    email_norm = email.strip().lower()
    user = db.execute(select(User).where(User.email == email_norm)).scalar_one_or_none()
    if user is None:
        # Do not reveal whether the email exists.
        logger.info("Password reset requested for unknown email %s - no-op", email_norm)
        return

    plain = generate_reset_token()
    now = datetime.now(timezone.utc)
    token_row = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_secret(plain),
        expires_at=now + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
    )
    db.add(token_row)
    db.commit()

    # Stub for real email delivery - logged instead of sent, per design doc non-goals.
    logger.info("Password reset link for %s: /auth/password-reset/confirm?token=%s", email_norm, plain)


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
    if user.status == "invited":
        user.status = "active"
    row.used_at = now
    db.commit()
