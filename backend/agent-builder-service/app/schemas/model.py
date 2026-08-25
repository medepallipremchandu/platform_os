import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ModelCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    provider: str = Field(pattern="^(claude|azure_openai)$")
    model_id: str = Field(min_length=1, description="Model name (Claude) or deployment name (Azure OpenAI)")
    api_key: str = Field(min_length=1)
    endpoint: str | None = Field(default=None, description="Required for azure_openai")
    api_version: str | None = Field(default=None, description="Required for azure_openai")


class ModelUpdateRequest(BaseModel):
    """Rename and/or re-enter credentials without deactivating and recreating the row.
    `provider`/`model_id` are intentionally not editable here - changing either is a different
    model deployment, so create a new one instead."""

    name: str | None = Field(default=None, min_length=1)
    api_key: str | None = Field(default=None, min_length=1, description="Re-encrypts and replaces the stored key")
    endpoint: str | None = Field(default=None, description="azure_openai only")
    api_version: str | None = Field(default=None, description="azure_openai only")


class ModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    model_code: str
    name: str
    provider: str
    model_id: str
    endpoint: str | None
    api_version: str | None
    is_active: bool
    created_by: str | None
    created_at: datetime
