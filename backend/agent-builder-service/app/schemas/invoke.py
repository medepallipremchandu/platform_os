import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class InvokeRequest(BaseModel):
    variables: dict[str, str] = {}


class InvokeResponse(BaseModel):
    output: Any
    provider_used: str


class InvocationLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    success: bool
    provider_used: str | None
    latency_ms: float
    error_message: str | None
    created_at: datetime
