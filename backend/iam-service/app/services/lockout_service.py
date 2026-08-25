"""Login lockout policy (design doc §4.2): lock an account for LOGIN_LOCKOUT_DURATION_MINUTES
after LOGIN_LOCKOUT_THRESHOLD failed attempts within a rolling LOGIN_LOCKOUT_WINDOW_MINUTES
window. All thresholds come from Settings - never hardcoded here."""
from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.models.user import User


def is_locked(user: User) -> bool:
    return user.locked_until is not None and user.locked_until > datetime.now(timezone.utc)


def register_failed_attempt(user: User, settings: Settings) -> None:
    now = datetime.now(timezone.utc)
    window = timedelta(minutes=settings.LOGIN_LOCKOUT_WINDOW_MINUTES)

    if user.first_failed_login_at is None or (now - user.first_failed_login_at) > window:
        user.first_failed_login_at = now
        user.failed_login_count = 1
    else:
        user.failed_login_count += 1

    if user.failed_login_count >= settings.LOGIN_LOCKOUT_THRESHOLD:
        user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCKOUT_DURATION_MINUTES)


def register_successful_attempt(user: User) -> None:
    user.failed_login_count = 0
    user.first_failed_login_at = None
    user.locked_until = None
