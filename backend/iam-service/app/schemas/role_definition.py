import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RoleDefinitionCreateRequest(BaseModel):
    organization_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    permission_codes: list[str] = Field(default_factory=list)


class RoleDefinitionUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    permission_codes: list[str] | None = None


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    description: str | None


class RoleDefinitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID | None
    name: str
    description: str | None
    is_builtin: bool
    archived_at: datetime | None
    created_at: datetime
    permissions: list[PermissionOut]
