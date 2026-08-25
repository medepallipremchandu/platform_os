import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ServicePrincipalCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    organization_id: uuid.UUID
    resource_type: str | None = None
    resource_id: str | None = None


class ServicePrincipalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    client_id: str
    resource_type: str | None
    resource_id: str | None
    revoked_at: datetime | None
    created_at: datetime


class ServicePrincipalCreatedResponse(BaseModel):
    service_principal: ServicePrincipalOut
    client_secret: str = Field(description="Shown exactly once - never recoverable after this response.")


class ServicePrincipalPreviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    client_id: str
    resource_type: str | None
    resource_id: str | None
    revoked_at: datetime | None
    created_at: datetime


class RotateSecretResponse(BaseModel):
    client_secret: str
