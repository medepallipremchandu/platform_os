from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.schemas.call_agents import CallScriptField


class InlineCallScript(BaseModel):
    persona: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    consent_line: str = Field(
        default="This call may be recorded and is conducted by an AI assistant. Do you consent to continue?"
    )
    closing_line: str = Field(default="Thanks for your time, have a great day!")
    fields: list[CallScriptField] = Field(default_factory=list)


class CallCreateRequest(BaseModel):
    to_number: str = Field(min_length=1, description="E.164 phone number to dial, e.g. +14155550123")
    webhook_url: str | None = Field(default=None, description="Caller's own endpoint notified on lifecycle events")
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Path 1: use a saved CallAgentConfig.
    call_agent_config_id: uuid.UUID | None = None

    # Path 2: fully inline, ad-hoc call - no saved config.
    telephony_provider_config_id: uuid.UUID | None = None
    call_script: InlineCallScript | None = None
    max_conversation_duration_minutes: int | None = Field(default=None, ge=1, le=60)

    @model_validator(mode="after")
    def _validate_exactly_one_path(self) -> "CallCreateRequest":
        if self.call_agent_config_id is not None:
            return self
        if self.telephony_provider_config_id is None or self.call_script is None or self.max_conversation_duration_minutes is None:
            raise ValueError(
                "Either call_agent_config_id, or all of "
                "(telephony_provider_config_id, call_script, max_conversation_duration_minutes) must be provided"
            )
        return self


class CancelCallRequest(BaseModel):
    graceful: bool = Field(default=True, description="If true, the AI wraps up politely before hanging up")


class CallResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    call_agent_config_id: uuid.UUID | None
    telephony_provider_config_id: uuid.UUID
    status: str
    to_number: str
    from_number: str
    max_duration_minutes: int
    webhook_url: str | None
    metadata: dict[str, Any]
    extracted_fields: dict[str, Any]
    consent_status: str | None
    end_reason: str | None
    retry_max_attempts: int
    retry_interval_minutes: int
    retry_on_statuses: list[str]
    attempt_number: int
    root_call_id: uuid.UUID | None
    next_retry_at: datetime | None
    created_by: str
    created_at: datetime
    connected_at: datetime | None
    ended_at: datetime | None


class CallListResponse(BaseModel):
    items: list[CallResponse]
    total: int
    limit: int
    offset: int


class CallEventResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


class ConversationTurnResponse(BaseModel):
    turn_index: int
    speaker: str
    text: str
    created_at: datetime


class CallSummaryResponse(BaseModel):
    summary_text: str
    extracted_fields: dict[str, Any]
    created_at: datetime
