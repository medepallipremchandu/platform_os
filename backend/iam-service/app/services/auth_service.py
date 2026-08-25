"""Login, client-credentials, refresh-rotation, org-switch, logout and password-reset flows.

Refresh token rotation & reuse detection (design doc §5): a refresh token is stored only as
a SHA-256 hash and rotated on every use. `family_id` is shared across a whole rotation
chain. If a caller presents a token whose hash matches a row that's already revoked, that's
evidence of theft/replay (someone used a token we already rotated away from) - the entire
family is revoked immediately.
"""
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.constants import ActorType, AuditResult
from app.core.exceptions import ConflictError, ForbiddenError, LockedError, UnauthorizedError
from app.core.password import hash_password, verify_password
from app.core.secrets import generate_client_id, generate_client_secret, hash_secret
from app.models.organization import Organization
from app.models.organization_membership import OrganizationMembership
from app.models.refresh_token import RefreshToken
from app.models.service_principal import ServicePrincipal
from app.models.user import User
from app.services import lockout_service
from app.services.audit_service import record_audit_event
from app.services.jwt_service import access_token_ttl_seconds, issue_access_token


def _generate_refresh_token_plain() -> str:
    return secrets.token_urlsafe(48)


def _active_memberships(db: Session, user_id: uuid.UUID) -> list[OrganizationMembership]:
    # Joined against Organization.is_active so a deactivated organization's users can no longer
    # authenticate into it - membership status alone isn't enough, since the membership row
    # itself is untouched when the *organization* (not the member) is deactivated.
    stmt = (
        select(OrganizationMembership)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == "active",
            Organization.is_active.is_(True),
        )
    )
    return list(db.execute(stmt).scalars().all())


def _create_refresh_token_row(
    db: Session, *, user_id: uuid.UUID, organization_id: uuid.UUID, family_id: uuid.UUID, settings: Settings
) -> tuple[RefreshToken, str]:
    plain = _generate_refresh_token_plain()
    now = datetime.now(timezone.utc)
    row = RefreshToken(
        token_hash=hash_secret(plain),
        family_id=family_id,
        user_id=user_id,
        organization_id=organization_id,
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(row)
    return row, plain


def _issue_pair_for_user(db: Session, *, user: User, organization_id: uuid.UUID | None, settings: Settings) -> dict:
    """`organization_id` is None only for a platform superadmin with no organization membership.
    That session carries org_id=null and permissions=[] - a superadmin's authority comes from
    the is_superadmin claim, not from org-scoped permissions it could not possibly have."""
    from app.services.permission_service import resolve_permissions

    permissions = (
        resolve_permissions(db, principal_type="user", principal_id=user.id, organization_id=organization_id)
        if organization_id is not None
        else []
    )
    access_token, _claims = issue_access_token(
        sub=user.id,
        principal_type="user",
        org_id=organization_id,
        permissions=permissions,
        email=user.email,
        is_superadmin=user.is_superadmin,
    )
    family_id = uuid.uuid4()
    _row, refresh_plain = _create_refresh_token_row(
        db, user_id=user.id, organization_id=organization_id, family_id=family_id, settings=settings
    )
    db.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh_plain,
        "token_type": "bearer",
        "expires_in": access_token_ttl_seconds(),
        "organization_id": organization_id,
    }


def login(
    db: Session,
    settings: Settings,
    *,
    email: str,
    password: str,
    organization_id: uuid.UUID | None,
    source_ip: str | None = None,
    user_agent: str | None = None,
) -> dict:
    email_norm = email.strip().lower()
    user = db.execute(select(User).where(User.email == email_norm)).scalar_one_or_none()

    def audit(org_id, result, action="login"):
        record_audit_event(
            db,
            organization_id=org_id,
            actor_type=ActorType.USER.value,
            actor_id=user.id if user else None,
            action=action,
            target_type="user",
            target_id=email_norm,
            result=result,
            source_ip=source_ip,
            user_agent=user_agent,
        )

    if user is None:
        audit(None, AuditResult.DENIED.value)
        raise UnauthorizedError("Invalid email or password")

    if lockout_service.is_locked(user):
        audit(None, AuditResult.DENIED.value, action="login_lockout")
        raise LockedError("Account is temporarily locked due to too many failed attempts")

    if user.status != "active" and user.status != "invited":
        audit(None, AuditResult.DENIED.value)
        raise UnauthorizedError("Account is disabled")

    if not user.password_hash or not verify_password(password, user.password_hash):
        lockout_service.register_failed_attempt(user, settings)
        just_locked = lockout_service.is_locked(user)
        db.commit()
        audit(None, AuditResult.DENIED.value, action="login_lockout" if just_locked else "login")
        if just_locked:
            raise LockedError("Account locked due to too many failed attempts")
        raise UnauthorizedError("Invalid email or password")

    lockout_service.register_successful_attempt(user)
    db.commit()

    memberships = _active_memberships(db, user.id)
    if not memberships:
        # A platform superadmin legitimately belongs to no organization - that IS the tier. Any
        # other user with no active membership has nothing to log into, so the existing refusal
        # stands for them.
        if user.is_superadmin:
            result = _issue_pair_for_user(db, user=user, organization_id=None, settings=settings)
            audit(None, AuditResult.SUCCESS.value)
            return result
        audit(None, AuditResult.DENIED.value)
        raise ForbiddenError("User has no active organization membership")

    if organization_id is not None:
        chosen = next((m for m in memberships if m.organization_id == organization_id), None)
        if chosen is None:
            audit(organization_id, AuditResult.DENIED.value)
            raise ForbiddenError("User is not an active member of the requested organization")
    elif len(memberships) == 1:
        chosen = memberships[0]
    else:
        audit(None, AuditResult.DENIED.value, action="login_ambiguous_org")
        raise ConflictError("User belongs to multiple organizations - specify organization_id")

    result = _issue_pair_for_user(db, user=user, organization_id=chosen.organization_id, settings=settings)
    audit(chosen.organization_id, AuditResult.SUCCESS.value)
    return result


def client_credentials_grant(db: Session, *, client_id: str, client_secret: str) -> dict:
    from app.services.permission_service import resolve_permissions

    sp = db.execute(select(ServicePrincipal).where(ServicePrincipal.client_id == client_id)).scalar_one_or_none()

    def audit(org_id, result):
        record_audit_event(
            db,
            organization_id=org_id,
            actor_type=ActorType.SERVICE_PRINCIPAL.value,
            actor_id=sp.id if sp else None,
            action="token_client_credentials",
            target_type="service_principal",
            target_id=client_id,
            result=result,
        )

    if sp is None or sp.is_revoked or hash_secret(client_secret) != sp.secret_hash:
        audit(sp.organization_id if sp else None, AuditResult.DENIED.value)
        raise UnauthorizedError("Invalid client credentials")

    permissions = resolve_permissions(
        db, principal_type="service_principal", principal_id=sp.id, organization_id=sp.organization_id
    )
    resource_scope = None
    if sp.resource_type and sp.resource_id:
        resource_scope = {"type": sp.resource_type, "id": sp.resource_id}

    access_token, _claims = issue_access_token(
        sub=sp.id,
        principal_type="service_principal",
        org_id=sp.organization_id,
        permissions=permissions,
        resource_scope=resource_scope,
        name=sp.name,
    )
    audit(sp.organization_id, AuditResult.SUCCESS.value)
    return {"access_token": access_token, "token_type": "bearer", "expires_in": access_token_ttl_seconds()}


def refresh_token_rotate(db: Session, settings: Settings, *, refresh_token_plain: str) -> dict:
    token_hash = hash_secret(refresh_token_plain)
    row = db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash)).scalar_one_or_none()

    if row is None:
        record_audit_event(
            db,
            organization_id=None,
            actor_type=ActorType.USER.value,
            actor_id=None,
            action="token_refresh",
            target_type="refresh_token",
            result=AuditResult.DENIED.value,
        )
        raise UnauthorizedError("Invalid refresh token")

    if row.revoked_at is not None:
        # Reuse of an already-rotated token: revoke the whole family (theft detection).
        stmt = select(RefreshToken).where(RefreshToken.family_id == row.family_id, RefreshToken.revoked_at.is_(None))
        now = datetime.now(timezone.utc)
        for sibling in db.execute(stmt).scalars().all():
            sibling.revoked_at = now
        db.commit()
        record_audit_event(
            db,
            organization_id=row.organization_id,
            actor_type=ActorType.USER.value,
            actor_id=row.user_id,
            action="token_refresh_reuse_detected",
            target_type="refresh_token",
            result=AuditResult.DENIED.value,
        )
        raise UnauthorizedError("Refresh token reuse detected - session revoked")

    now = datetime.now(timezone.utc)
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        record_audit_event(
            db,
            organization_id=row.organization_id,
            actor_type=ActorType.USER.value,
            actor_id=row.user_id,
            action="token_refresh",
            target_type="refresh_token",
            result=AuditResult.DENIED.value,
        )
        raise UnauthorizedError("Refresh token expired")

    user = db.get(User, row.user_id)
    if user is None or user.status == "disabled":
        raise UnauthorizedError("Account is disabled")

    row.revoked_at = now

    from app.services.permission_service import resolve_permissions

    permissions = (
        resolve_permissions(db, principal_type="user", principal_id=user.id, organization_id=row.organization_id)
        if row.organization_id is not None
        else []
    )
    access_token, _claims = issue_access_token(
        sub=user.id,
        principal_type="user",
        org_id=row.organization_id,
        permissions=permissions,
        email=user.email,
        is_superadmin=user.is_superadmin,
    )
    _new_row, new_refresh_plain = _create_refresh_token_row(
        db, user_id=user.id, organization_id=row.organization_id, family_id=row.family_id, settings=settings
    )
    db.commit()

    record_audit_event(
        db,
        organization_id=row.organization_id,
        actor_type=ActorType.USER.value,
        actor_id=user.id,
        action="token_refresh",
        target_type="refresh_token",
        result=AuditResult.SUCCESS.value,
    )
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_plain,
        "token_type": "bearer",
        "expires_in": access_token_ttl_seconds(),
    }


def switch_org(db: Session, settings: Settings, *, user_id: uuid.UUID, organization_id: uuid.UUID) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("Account is disabled")

    membership = db.execute(
        select(OrganizationMembership)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.status == "active",
            Organization.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if membership is None:
        # A platform superadmin may scope a session to any ACTIVE organization without holding a
        # membership - overseeing every tenant is the tier's purpose, and GET /organizations
        # already shows them all, so a switcher listing organizations they cannot enter would be
        # a dead end.
        #
        # This grants scope, not authority: permissions still come only from role assignments
        # they actually hold in that organization (usually none), so the resulting token carries
        # an empty permission list plus is_superadmin. Superadmin-gated endpoints work; org-scoped
        # ones stay closed unless someone deliberately assigned them a role there.
        organization = db.get(Organization, organization_id)
        if not (user.is_superadmin and organization is not None and organization.is_active):
            raise ForbiddenError("User is not an active member of the requested organization")

    result = _issue_pair_for_user(db, user=user, organization_id=organization_id, settings=settings)
    record_audit_event(
        db,
        organization_id=organization_id,
        actor_type=ActorType.USER.value,
        actor_id=user_id,
        action="switch_org",
        target_type="organization",
        target_id=str(organization_id),
        result=AuditResult.SUCCESS.value,
    )
    return result


def logout(db: Session, *, user_id: uuid.UUID) -> None:
    now = datetime.now(timezone.utc)
    stmt = select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
    for row in db.execute(stmt).scalars().all():
        row.revoked_at = now
    db.commit()
    record_audit_event(
        db,
        organization_id=None,
        actor_type=ActorType.USER.value,
        actor_id=user_id,
        action="logout",
        target_type="user",
        target_id=str(user_id),
        result=AuditResult.SUCCESS.value,
    )


def create_service_principal_credentials() -> tuple[str, str, str]:
    """Returns (client_id, client_secret_plain, client_secret_hash)."""
    client_id = generate_client_id()
    client_secret = generate_client_secret()
    return client_id, client_secret, hash_secret(client_secret)
