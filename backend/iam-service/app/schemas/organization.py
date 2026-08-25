import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class OrganizationCreateRequest(BaseModel):
    """Superadmin-only tenant provisioning: the organization, its permission ceiling and its
    first admin arrive together, because a tenant with no admin is not usable and a tenant with
    no ceiling could grant nothing."""

    name: str = Field(min_length=1, max_length=255)
    admin_email: EmailStr
    admin_display_name: str | None = Field(default=None, max_length=255)
    allowed_permission_codes: list[str] = Field(min_length=1)


class OrganizationUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class OrganizationEntitlementsRequest(BaseModel):
    """The full replacement set of permission codes this organization may grant. An empty list
    clears the ceiling back to unrestricted - which is a real, deliberate choice, so it is
    allowed here even though creation requires at least one."""

    allowed_permission_codes: list[str]


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_active: bool
    # None means unrestricted, not "none allowed" - see Organization.allowed_permissions.
    allowed_permissions: list[str] | None = None
    created_at: datetime


class OrganizationWithAdminOut(BaseModel):
    organization: OrganizationOut
    admin: "OrganizationAdminOut"


class OrganizationAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None
    status: str


OrganizationWithAdminOut.model_rebuild()
