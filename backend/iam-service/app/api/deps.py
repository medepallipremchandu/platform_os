"""Auth dependencies for iam-service's own endpoints (it is a relying party on its own
tokens, same as every other platform service - see design doc §7). `require_permission`
also records a denied audit event for every permission check that fails on iam-service's own
API surface, per the platform team's audit requirement."""
import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.revoked_token_jti import RevokedTokenJti
from app.services.jwt_service import decode_access_token


@dataclass
class CurrentActor:
    principal_type: str
    id: uuid.UUID
    org_id: uuid.UUID | None
    permissions: list[str]
    is_superadmin: bool = False
    resource_scope: dict | None = None
    email: str | None = None
    name: str | None = None
    jti: str | None = None


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header")
    return authorization.split(" ", 1)[1].strip()


def current_actor(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> CurrentActor:
    token = _extract_bearer_token(authorization)
    try:
        claims = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    jti = claims.get("jti")
    if jti and db.get(RevokedTokenJti, jti) is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    org_id = uuid.UUID(claims["org_id"]) if claims.get("org_id") else None
    return CurrentActor(
        principal_type=claims["principal_type"],
        id=uuid.UUID(claims["sub"]),
        org_id=org_id,
        permissions=claims.get("permissions", []),
        is_superadmin=bool(claims.get("is_superadmin")),
        resource_scope=claims.get("resource_scope"),
        email=claims.get("email"),
        name=claims.get("name"),
        jti=jti,
    )


def require_permission(permission_code: str):
    """Gate an endpoint on one permission code.

    A platform superadmin satisfies every check here. That is the definition of the tier, not a
    shortcut: they hold no organization membership and therefore no org-scoped permissions at
    all, so without this they could create a tenant and its first admin and then be locked out
    of that tenant forever - unable to appoint a replacement admin if the first one left. The
    endpoints this guards all take their organization from the path or body rather than from the
    caller's token, so the bypass grants reach without smuggling in any ambient scope.

    `require_superadmin` remains the separate, exclusive gate for platform-tier actions."""

    def _dependency(
        actor: CurrentActor = Depends(current_actor),
        db: Session = Depends(get_db),
    ) -> CurrentActor:
        if actor.is_superadmin:
            return actor
        if permission_code not in actor.permissions:
            from app.core.constants import ActorType, AuditResult
            from app.services.audit_service import record_audit_event

            record_audit_event(
                db,
                organization_id=actor.org_id,
                actor_type=actor.principal_type,
                actor_id=actor.id,
                action=f"permission_check:{permission_code}",
                target_type="permission",
                target_id=permission_code,
                result=AuditResult.DENIED.value,
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing permission: {permission_code}")
        return actor

    return _dependency


def require_superadmin(
    actor: CurrentActor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> CurrentActor:
    """The platform tier, checked as its own axis - NOT as a permission.

    The relationship with require_permission is deliberately ONE-WAY: a superadmin satisfies
    every permission check, but no set of permissions ever satisfies this one. A user holding
    every talentos.iam.* permission inside some organization is an extremely powerful
    organization admin, and still must not be able to create organizations, set another tenant's
    entitlement ceiling, or reach across tenants. Only the is_superadmin claim - set from
    User.is_superadmin, and granted only by scripts/bootstrap.py - opens that door.

    Denials are audited like any other failed authorization check on iam-service's own surface.
    """
    if not actor.is_superadmin:
        from app.core.constants import AuditResult
        from app.services.audit_service import record_audit_event

        record_audit_event(
            db,
            organization_id=actor.org_id,
            actor_type=actor.principal_type,
            actor_id=actor.id,
            action="superadmin_check",
            target_type="platform",
            target_id=None,
            result=AuditResult.DENIED.value,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This action requires platform superadmin privileges"
        )
    return actor


__all__ = ["get_db", "current_actor", "require_permission", "require_superadmin", "CurrentActor"]
