import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentActor, current_actor, get_db, require_permission, require_superadmin
from app.config import Settings, get_settings
from app.core.constants import AuditResult
from app.schemas.organization import (
    OrganizationAdminOut,
    OrganizationCreateRequest,
    OrganizationEntitlementsRequest,
    OrganizationOut,
    OrganizationUpdateRequest,
    OrganizationWithAdminOut,
)
from app.schemas.user import MembershipUpdateRequest, OrganizationMemberOut, UserInviteRequest, UserOut
from app.services import organization_service, user_service
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationWithAdminOut, status_code=201)
def create_organization(
    payload: OrganizationCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    actor: CurrentActor = Depends(require_superadmin),
):
    """Superadmin-only, and gated on the platform tier rather than on
    talentos.iam.organizations.manage: creating tenants and setting their ceilings sits above
    every organization, so no org-scoped permission - however broad - should reach it.

    One call provisions the whole tenant: organization, permission ceiling, first admin, that
    admin's Organization Admin assignment, and the invite email."""
    org, admin = organization_service.create_organization_with_admin(
        db,
        settings,
        name=payload.name,
        admin_email=payload.admin_email,
        admin_display_name=payload.admin_display_name,
        allowed_permission_codes=payload.allowed_permission_codes,
    )
    record_audit_event(
        db,
        organization_id=org.id,
        actor_type=actor.principal_type,
        actor_id=actor.id,
        action="organization.created",
        target_type="organization",
        target_id=str(org.id),
        result=AuditResult.SUCCESS.value,
        source_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        changes={
            "name": {"old": None, "new": org.name},
            "admin_email": {"old": None, "new": admin.email},
            "allowed_permissions": {"old": None, "new": org.allowed_permissions},
        },
    )
    return OrganizationWithAdminOut(
        organization=OrganizationOut.model_validate(org), admin=OrganizationAdminOut.model_validate(admin)
    )


@router.get("", response_model=list[OrganizationOut])
def list_organizations(actor: CurrentActor = Depends(current_actor), db: Session = Depends(get_db)):
    """What the caller can see, not what exists. A superadmin gets every organization
    platform-wide (that is the tier's whole job); a service principal gets its own; a user gets
    the ones they are an active member of."""
    if actor.is_superadmin:
        return organization_service.list_all_organizations(db)
    if actor.principal_type == "service_principal":
        from app.models.organization import Organization

        org = db.get(Organization, actor.org_id)
        return [org] if org else []
    return organization_service.list_organizations_for_user(db, actor.id)


@router.patch("/{organization_id}/entitlements", response_model=OrganizationOut)
def set_entitlements(
    organization_id: uuid.UUID,
    payload: OrganizationEntitlementsRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(require_superadmin),
):
    """Superadmin-only: raise or lower what this organization is allowed to grant at all.

    Lowering it is immediate and needs no other change - the ceiling is intersected at token
    issuance, so a permission removed here stops appearing on the very next token even though
    every role still nominally grants it."""
    org = organization_service.set_entitlements(
        db, organization_id, allowed_permission_codes=payload.allowed_permission_codes
    )
    record_audit_event(
        db,
        organization_id=organization_id,
        actor_type=actor.principal_type,
        actor_id=actor.id,
        action="organization.entitlements_updated",
        target_type="organization",
        target_id=str(organization_id),
        result=AuditResult.SUCCESS.value,
        source_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        changes={"allowed_permissions": {"old": None, "new": org.allowed_permissions}},
    )
    return org


@router.patch("/{organization_id}", response_model=OrganizationOut)
def rename_organization(
    organization_id: uuid.UUID,
    payload: OrganizationUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(require_permission("talentos.iam.organizations.manage")),
):
    org = organization_service.rename_organization(db, organization_id, name=payload.name)
    record_audit_event(
        db,
        organization_id=organization_id,
        actor_type=actor.principal_type,
        actor_id=actor.id,
        action="organization.renamed",
        target_type="organization",
        target_id=str(organization_id),
        result=AuditResult.SUCCESS.value,
        source_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        changes={"name": {"old": None, "new": payload.name}},
    )
    return org


@router.post("/{organization_id}/deactivate", response_model=OrganizationOut)
def deactivate_organization(
    organization_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(require_permission("talentos.iam.organizations.manage")),
):
    org = organization_service.deactivate_organization(db, organization_id)
    record_audit_event(
        db,
        organization_id=organization_id,
        actor_type=actor.principal_type,
        actor_id=actor.id,
        action="organization.deactivated",
        target_type="organization",
        target_id=str(organization_id),
        result=AuditResult.SUCCESS.value,
        source_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return org


@router.post("/{organization_id}/reactivate", response_model=OrganizationOut)
def reactivate_organization(
    organization_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(require_permission("talentos.iam.organizations.manage")),
):
    org = organization_service.reactivate_organization(db, organization_id)
    record_audit_event(
        db,
        organization_id=organization_id,
        actor_type=actor.principal_type,
        actor_id=actor.id,
        action="organization.reactivated",
        target_type="organization",
        target_id=str(organization_id),
        result=AuditResult.SUCCESS.value,
        source_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return org


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
    # Hand-rolled rather than require_permission, because plain membership is also enough here:
    # anyone in an organization may see who else is in it. The superadmin arm has to be spelled
    # out for the same reason it does in require_permission - they hold no org-scoped permissions
    # and belong to no organization, so both of the other two tests are false for them.
    has_permission = "talentos.iam.users.manage" in actor.permissions
    is_member = actor.principal_type == "user" and actor.org_id == organization_id
    if not (actor.is_superadmin or has_permission or is_member):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing permission: talentos.iam.users.manage")

    memberships = user_service.list_organization_members(db, organization_id)
    return [_member_out(m) for m in memberships]


@router.patch("/{organization_id}/users/{user_id}", response_model=OrganizationMemberOut)
def update_user_membership(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: MembershipUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(require_permission("talentos.iam.users.manage")),
):
    membership = user_service.update_membership(
        db, organization_id, user_id, status=payload.status, display_name=payload.display_name
    )
    changes = {}
    if payload.status is not None:
        changes["status"] = {"old": None, "new": payload.status}
    if payload.display_name is not None:
        changes["display_name"] = {"old": None, "new": payload.display_name}
    record_audit_event(
        db,
        organization_id=organization_id,
        actor_type=actor.principal_type,
        actor_id=actor.id,
        action="user.membership_updated",
        target_type="user",
        target_id=str(user_id),
        result=AuditResult.SUCCESS.value,
        source_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        changes=changes or None,
    )
    return _member_out(membership)
