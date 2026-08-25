import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RoleAssignmentCreateRequest(BaseModel):
    principal_type: str = Field(pattern="^(user|service_principal)$")
    principal_id: uuid.UUID
    role_definition_id: uuid.UUID
    organization_id: uuid.UUID
    scope_type: str = Field(pattern="^(organization|service)$")
    service_name: str | None = None  # required when scope_type == "service"

    @model_validator(mode="after")
    def _check_service_name(self):
        if self.scope_type == "service" and not self.service_name:
            raise ValueError("service_name is required when scope_type is 'service'")
        return self


class RoleAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    principal_type: str
    principal_id: uuid.UUID
    role_definition_id: uuid.UUID
    role_definition_name: str | None = None
    organization_id: uuid.UUID
    scope_type: str
    scope_id: str
    created_at: datetime
