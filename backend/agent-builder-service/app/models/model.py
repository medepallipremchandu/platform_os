import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

PROVIDERS = ("claude", "azure_openai")


class Model(Base):
    """A registered, ready-to-use model deployment - the catalog agents pick from.
    Credentials are encrypted at rest; only platform admins register these."""

    __tablename__ = "models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    model_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)  # claude | azure_openai
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g. claude-sonnet-5, or deployment name
    endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)  # azure_openai only
    api_version: Mapped[str | None] = mapped_column(String(50), nullable=True)  # azure_openai only
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
