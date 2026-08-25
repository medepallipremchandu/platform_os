import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JDCallAgentConfigRequest(BaseModel):
    call_agent_config_id: str
    enabled: bool = True


class JDCallAgentConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    call_agent_config_id: str
    enabled: bool


class SubmissionCallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    submission_id: uuid.UUID
    voice_agent_call_id: str
    status: str
    attempt_number: int
    summary_text: str | None
    extracted_fields: dict | None
    end_reason: str | None
    triggered_by: str | None
    created_at: datetime
    updated_at: datetime | None


class ConversationTurnResponse(BaseModel):
    # `id` is optional: the fixed contract this was built against listed one, but the live
    # voice-agent-service's own ConversationTurnResponse doesn't actually include it (verified
    # against its real /openapi.json once it became reachable) - kept optional here rather than
    # dropped entirely in case a future version adds it back.
    id: str | None = None
    turn_index: int
    speaker: str
    text: str
    created_at: datetime
