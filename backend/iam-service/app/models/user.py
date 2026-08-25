import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

USER_STATUSES = ("invited", "active", "disabled")


class User(Base):
    """Human identity. One User row per person platform-wide; OrganizationMembership rows
    are how one person can belong to several organizations (see that model's docstring)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="invited")

    # The platform tier above organizations: creates organizations and their first admin, and
    # sets each organization's permission ceiling. Deliberately a flag on the user rather than a
    # role or permission - a superadmin has no organization membership, so there is no org scope
    # for a RoleAssignment to hang off, and holding every talentos.iam.* permission INSIDE some
    # organization must never add up to being a platform superadmin. See
    # app/api/deps.py::require_superadmin.
    is_superadmin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # MFA - schema support only, per design doc §1 non-goals. No enrollment/verification flow
    # is implemented in this build.
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mfa_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Login lockout tracking (rolling window - see Settings.LOGIN_LOCKOUT_*)
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_failed_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_locked(self) -> bool:
        return self.locked_until is not None and self.locked_until > datetime.now(self.locked_until.tzinfo)
