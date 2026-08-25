from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RevokedTokenJti(Base):
    """Emergency-only deny-list (design doc §5): a cheap indexed lookup alongside signature
    validation for the rare 'kill this access token right now' case (e.g. a compromised
    service principal secret), without waiting out the token's normal ~15 minute lifetime."""

    __tablename__ = "revoked_token_jti"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
