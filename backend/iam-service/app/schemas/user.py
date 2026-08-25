import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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
    status: str = Field(pattern="^(active|disabled)$")
