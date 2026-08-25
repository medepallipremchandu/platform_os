from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CallScriptField(BaseModel):
    name: str = Field(min_length=1, description="Key the extracted value will be stored under")
    type: Literal["string", "boolean", "number", "date"] = "string"
    description: str = Field(min_length=1, description="What the AI should try to capture, in plain English")


class CallAgentConfigCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    persona: str = Field(min_length=1, description="Who the AI is, e.g. 'You are Ava, a scheduling assistant for Acme Dental.'")
    objective: str = Field(min_length=1, description="What the call is trying to accomplish")
    consent_line: str = Field(
        default="This call may be recorded and is conducted by an AI assistant. Do you consent to continue?"
    )
    closing_line: str = Field(default="Thanks for your time, have a great day!")
    fields: list[CallScriptField] = Field(default_factory=list)
    max_conversation_duration_minutes: int = Field(default=10, ge=1, le=60)
    retry_max_attempts: int = Field(default=0, ge=0, le=10)
    retry_interval_minutes: int = Field(default=30, ge=1, le=1440)
    retry_on_statuses: list[str] = Field(default_factory=lambda: ["NO_ANSWER", "BUSY"])
    telephony_provider_config_id: uuid.UUID
    visibility: Literal["organization", "restricted"] = "organization"
    grant_user_ids: list[str] = Field(default_factory=list, description="Only used when visibility='restricted'")


class CallAgentConfigUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    persona: str | None = None
    objective: str | None = None
    consent_line: str | None = None
    closing_line: str | None = None
    fields: list[CallScriptField] | None = None
    max_conversation_duration_minutes: int | None = Field(default=None, ge=1, le=60)
    retry_max_attempts: int | None = Field(default=None, ge=0, le=10)
    retry_interval_minutes: int | None = Field(default=None, ge=1, le=1440)
    retry_on_statuses: list[str] | None = None
    telephony_provider_config_id: uuid.UUID | None = None
    visibility: Literal["organization", "restricted"] | None = None
    grant_user_ids: list[str] | None = None
    is_active: bool | None = None


class CallAgentConfigResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None
    persona: str
    objective: str
    consent_line: str
    closing_line: str
    fields: list[CallScriptField]
    max_conversation_duration_minutes: int
    retry_max_attempts: int
    retry_interval_minutes: int
    retry_on_statuses: list[str]
    telephony_provider_config_id: uuid.UUID
    visibility: str
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


class CallAgentConfigListResponse(BaseModel):
    items: list[CallAgentConfigResponse]
