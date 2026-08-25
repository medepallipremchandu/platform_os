import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Organization(Base):
    """Top-level tenant boundary. Every resource platform-wide belongs to exactly one org.

    A tenant root is never hard-deleted - `is_active=False` (deactivated) is the only removal
    path, and it's enforced at login (see auth_service.login): a deactivated org's users can no
    longer authenticate into it."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # The entitlement CEILING a superadmin sets for this tenant: a list of permission codes this
    # organization is allowed to grant at all. NULL or empty means unrestricted.
    #
    # This is not a second permission system - it is an intersection applied at the one place
    # that matters, permission_service.resolve_permissions, which runs on every token issuance.
    # A role granting something outside the ceiling therefore simply never puts it on a token,
    # no matter how the role was authored or assigned. Unrestricted-by-default is what keeps the
    # feature additive: organizations created before entitlements existed are untouched.
    allowed_permissions: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
