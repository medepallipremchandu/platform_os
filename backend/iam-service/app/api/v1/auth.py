from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentActor, current_actor, get_db
from app.config import Settings, get_settings
from app.core.exceptions import ConflictError
from app.schemas.auth import (
    ClientCredentialsRequest,
    ClientCredentialsResponse,
    LoginRequest,
    MembershipChoice,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    RefreshTokenResponse,
    SwitchOrgRequest,
    TokenResponse,
)
from app.services import auth_service, password_reset_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    try:
        result = auth_service.login(
            db,
            settings,
            email=payload.email,
            password=payload.password,
            organization_id=payload.organization_id,
            source_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except ConflictError:
        from sqlalchemy import select

        from app.models.organization import Organization
        from app.models.organization_membership import OrganizationMembership
        from app.models.user import User

        user = db.execute(select(User).where(User.email == payload.email.strip().lower())).scalar_one_or_none()
        memberships = []
        if user is not None:
            rows = db.execute(
                select(OrganizationMembership, Organization)
                .join(Organization, Organization.id == OrganizationMembership.organization_id)
                .where(OrganizationMembership.user_id == user.id, OrganizationMembership.status == "active")
            ).all()
            memberships = [
                MembershipChoice(organization_id=org.id, organization_name=org.name).model_dump(mode="json")
                for _m, org in rows
            ]
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "User belongs to multiple organizations - specify organization_id",
                "memberships": memberships,
            },
        )
    return result


@router.post("/token", response_model=ClientCredentialsResponse)
def client_credentials(payload: ClientCredentialsRequest, db: Session = Depends(get_db)):
    return auth_service.client_credentials_grant(db, client_id=payload.client_id, client_secret=payload.client_secret)


@router.post("/token/refresh", response_model=RefreshTokenResponse)
def refresh(payload: RefreshTokenRequest, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    return auth_service.refresh_token_rotate(db, settings, refresh_token_plain=payload.refresh_token)


@router.post("/token/switch-org", response_model=RefreshTokenResponse)
def switch_org(
    payload: SwitchOrgRequest,
    actor: CurrentActor = Depends(current_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    return auth_service.switch_org(db, settings, user_id=actor.id, organization_id=payload.organization_id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(actor: CurrentActor = Depends(current_actor), db: Session = Depends(get_db)):
    auth_service.logout(db, user_id=actor.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
def password_reset_request(payload: PasswordResetRequest, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    password_reset_service.request_password_reset(db, settings, email=payload.email)
    return {"detail": "If that email exists, a reset link has been sent"}


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def password_reset_confirm(payload: PasswordResetConfirm, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    password_reset_service.confirm_password_reset(db, settings, token=payload.token, new_password=payload.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
