import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserInviteRequest(BaseModel):
    email: EmailStr
    display_name: str | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None
    status: str
    created_at: datetime


class OrganizationMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    display_name: str | None
    membership_status: str
    user_status: str
    created_at: datetime


class MembershipUpdateRequest(BaseModel):
    """`status` toggles the membership (active/disabled); `display_name` edits the underlying
    user record. Both optional so a caller can update either independently, but at least one
    must be given."""

    status: str | None = Field(default=None, pattern="^(active|disabled)$")
    display_name: str | None = Field(default=None, min_length=1, max_length=255)

    @model_validator(mode="after")
    def _require_at_least_one_field(self):
        if self.status is None and self.display_name is None:
            raise ValueError("At least one of status or display_name must be provided")
        return self
