from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TelephonyProviderCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    provider: str = Field(min_length=1, description="e.g. 'twilio' - open string, see get_telephony_provider")
    phone_number: str = Field(min_length=1, description="E.164 number this provider dials from")
    credentials: dict = Field(description="Provider-specific fields, e.g. {accountSid, authToken, fromNumber} for twilio")
    visibility: Literal["organization", "restricted"] = "organization"
    grant_user_ids: list[str] = Field(default_factory=list, description="Only used when visibility='restricted'")


class TelephonyProviderUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    phone_number: str | None = Field(default=None, min_length=1, description="E.164 number this provider dials from")
    credentials: dict | None = Field(
        default=None, description="If supplied, replaces the stored credentials (re-encrypted). Omit to keep existing."
    )


class TelephonyProviderResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    provider: str
    phone_number: str
    visibility: str
    created_by: str
    created_at: datetime
    revoked_at: datetime | None
    # credentials are never included, at rest or in transit, in any response.


class TelephonyProviderListResponse(BaseModel):
    items: list[TelephonyProviderResponse]
