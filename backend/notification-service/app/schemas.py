import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.providers.registry import PROVIDER_KINDS

_KIND_PATTERN = "^(" + "|".join(PROVIDER_KINDS) + ")$"


class ProviderFieldOut(BaseModel):
    name: str
    label: str
    type: str
    required: bool
    secret: bool
    default: object | None = None
    help: str | None = None
    placeholder: str | None = None


class ProviderSpecOut(BaseModel):
    kind: str
    key: str
    label: str
    description: str
    fields: list[ProviderFieldOut]


class ProviderConfigCreate(BaseModel):
    kind: str = Field(pattern=_KIND_PATTERN)
    provider: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=255)
    config: dict = Field(default_factory=dict)
    is_enabled: bool = False


class ProviderConfigUpdate(BaseModel):
    """Every field optional so a caller can rename, reconfigure or toggle independently.
    Omitting a secret inside `config` keeps the stored value - the API never returns secrets,
    so a round-tripped form has nothing to resend."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    config: dict | None = None
    is_enabled: bool | None = None


class ProviderConfigOut(BaseModel):
    """Note what is absent: `secrets_encrypted` and any secret field inside `config`. Secrets
    are write-only, the same posture iam-service takes with service-principal secrets."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    kind: str
    provider: str
    name: str
    config: dict
    is_enabled: bool
    # Which declared secret fields actually have a stored value, so the console can render
    # "password: set" without ever seeing it.
    secrets_set: list[str] = Field(default_factory=list)
    last_test_at: datetime | None = None
    last_test_ok: bool | None = None
    last_test_message: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    archived_at: datetime | None = None


class ProviderTestResult(BaseModel):
    ok: bool
    message: str


class EmailLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID | None
    to_email: str
    template: str
    status: str
    provider: str | None
    provider_scope: str | None
    error_message: str | None
    created_at: datetime
    sent_at: datetime | None


class EmailLogPage(BaseModel):
    items: list[EmailLogOut]
    total: int
    limit: int
    offset: int


class ResolvedProvidersOut(BaseModel):
    """What an organization's notifications will ACTUALLY use right now, after the
    organization-config-or-platform-default fallback has been applied. The console shows this
    so an operator never has to infer effective behaviour from a list of rows."""

    email_provider: str
    email_scope: str
    queue_provider: str
    queue_scope: str
