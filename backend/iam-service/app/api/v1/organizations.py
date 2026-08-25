import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentActor, current_actor, get_db, require_permission
from app.config import Settings, get_settings
from app.core.exceptions import ForbiddenError
from app.schemas.organization import OrganizationCreateRequest, OrganizationOut
from app.schemas.user import MembershipUpdateRequest, OrganizationMemberOut, UserInviteRequest, UserOut
from app.services import organization_service, user_service

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationOut, status_code=201)
def create_organization(
    payload: OrganizationCreateRequest,
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(require_permission("talentos.iam.organizations.manage")),
):
    return organization_service.create_organization(db, name=payload.name)


@router.get("", response_model=list[OrganizationOut])
def list_organizations(actor: CurrentActor = Depends(current_actor), db: Session = Depends(get_db)):
    if actor.principal_type == "service_principal":
        from app.models.organization import Organization

        org = db.get(Organization, actor.org_id)
        return [org] if org else []
    return organization_service.list_organizations_for_user(db, actor.id)


@router.post("/{organization_id}/users", response_model=UserOut, status_code=201)
def invite_user(
    organization_id: uuid.UUID,
    payload: UserInviteRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _actor: CurrentActor = Depends(require_permission("talentos.iam.users.invite")),
):
    return user_service.invite_user(
        db, settings, organization_id=organization_id, email=payload.email, display_name=payload.display_name
    )


def _member_out(membership) -> OrganizationMemberOut:
    return OrganizationMemberOut(
        id=membership.id,
        user_id=membership.user_id,
        email=membership.user.email,
        display_name=membership.user.display_name,
        membership_status=membership.status,
        user_status=membership.user.status,
        created_at=membership.created_at,
    )


@router.get("/{organization_id}/users", response_model=list[OrganizationMemberOut])
def list_users(
    organization_id: uuid.UUID,
    actor: CurrentActor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    has_permission = "talentos.iam.users.manage" in actor.permissions
    is_member = actor.principal_type == "user" and actor.org_id == organization_id
    if not (has_permission or is_member):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing permission: talentos.iam.users.manage")

    memberships = user_service.list_organization_members(db, organization_id)
    return [_member_out(m) for m in memberships]


@router.patch("/{organization_id}/users/{user_id}", response_model=OrganizationMemberOut)
def update_user_membership(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: MembershipUpdateRequest,
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(require_permission("talentos.iam.users.manage")),
):
    membership = user_service.update_membership_status(db, organization_id, user_id, payload.status)
    return _member_out(membership)
