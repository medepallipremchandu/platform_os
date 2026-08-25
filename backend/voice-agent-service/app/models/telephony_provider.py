from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TelephonyProviderConfig(Base):
    """A registered telephony provider credential (e.g. a Twilio account) an org can place
    calls through. `provider` is a free string, not an enum - see
    app/providers/telephony.get_telephony_provider - so adding a new provider later is just a
    new adapter + a new registry entry, no schema change.
    """

    __tablename__ = "telephony_provider_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    # Fernet-encrypted JSON blob of provider-specific fields (e.g. {accountSid, authToken,
    # fromNumber} for twilio) - see app/core/crypto.py. Never returned in any API response.
    encrypted_credentials: Mapped[str] = mapped_column(String, nullable=False)
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="organization")  # organization | restricted
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    grants: Mapped[list["TelephonyProviderConfigGrant"]] = relationship(
        back_populates="provider_config", cascade="all, delete-orphan"
    )


class TelephonyProviderConfigGrant(Base):
    """Only rows exist when the parent TelephonyProviderConfig.visibility == 'restricted' - one
    row per additional user (beyond the creator) allowed to see/use it."""

    __tablename__ = "telephony_provider_config_grants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("telephony_provider_configs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)

    provider_config: Mapped["TelephonyProviderConfig"] = relationship(back_populates="grants")
