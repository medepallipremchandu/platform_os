import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    organization_id: uuid.UUID | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    organization_id: uuid.UUID


class MembershipChoice(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organization_id: uuid.UUID
    organization_name: str


class MultipleOrganizationsError(BaseModel):
    detail: str = "User belongs to multiple organizations - specify organization_id"
    memberships: list[MembershipChoice]


class ClientCredentialsRequest(BaseModel):
    client_id: str
    client_secret: str


class ClientCredentialsResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class SwitchOrgRequest(BaseModel):
    organization_id: uuid.UUID


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=1)
