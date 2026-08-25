import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuditEventCreateRequest(BaseModel):
    action: str = Field(min_length=1, max_length=255)
    target_type: str = Field(min_length=1, max_length=100)
    target_id: str | None = None
    result: str = Field(pattern="^(success|denied|error)$")
    correlation_id: str | None = None
    source_ip: str | None = None
    user_agent: str | None = None
    changes: dict | None = None


class AuditLogEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID | None
    occurred_at: datetime
    actor_type: str
    actor_id: uuid.UUID | None
    action: str
    target_type: str
    target_id: str | None
    result: str
    correlation_id: str | None
    source_ip: str | None
    user_agent: str | None
    changes: dict | None


class AuditLogPage(BaseModel):
    items: list[AuditLogEntryOut]
    total: int
    limit: int
    offset: int
