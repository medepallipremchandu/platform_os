import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.model import ModelOut


class AgentCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    system_prompt: str = Field(min_length=1)
    user_prompt_template: str = Field(min_length=1)
    primary_model_id: uuid.UUID
    fallback_model_id: uuid.UUID | None = None
    max_output_tokens: int | None = Field(default=None, ge=256, le=64000)
    timeout_seconds: float | None = Field(default=None, ge=5, le=300)
    rate_limit_per_minute: int | None = Field(default=None, ge=1, le=6000)


class AgentUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    user_prompt_template: str | None = None
    primary_model_id: uuid.UUID | None = None
    fallback_model_id: uuid.UUID | None = None
    max_output_tokens: int | None = Field(default=None, ge=256, le=64000)
    timeout_seconds: float | None = Field(default=None, ge=5, le=300)
    rate_limit_per_minute: int | None = Field(default=None, ge=1, le=6000)


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    agent_code: str
    name: str
    description: str | None
    system_prompt: str
    user_prompt_template: str
    input_variables: list[str]
    primary_model: ModelOut
    fallback_model: ModelOut | None
    max_output_tokens: int
    timeout_seconds: float
    rate_limit_per_minute: int
    status: str
    created_by: str | None
    created_at: datetime
    updated_at: datetime | None
    published_at: datetime | None
    archived_at: datetime | None


class AgentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_code: str
    name: str
    status: str
    primary_model: ModelOut
    created_by: str | None
    created_at: datetime
    archived_at: datetime | None


class PublishResponse(BaseModel):
    agent: AgentOut
    client_secret: str | None = Field(
        default=None,
        description=(
            "The iam-service ServicePrincipal client_secret for this agent's invoke credential. "
            "Only present the first time this agent is published - shown once, never recoverable "
            "after this response. Exchange it (with the credential's client_id) for a Bearer "
            "token via iam-service's POST /auth/token to call /invoke."
        ),
    )


class RegenerateKeyResponse(BaseModel):
    client_secret: str = Field(description="Shown exactly once - never recoverable after this response.")


class AgentCredentialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: str
    created_at: datetime
    revoked_at: datetime | None
