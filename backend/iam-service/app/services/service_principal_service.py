import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.secrets import generate_client_id, generate_client_secret, hash_secret
from app.models.service_principal import ServicePrincipal


def create_service_principal(
    db: Session,
    *,
    organization_id: uuid.UUID,
    name: str,
    resource_type: str | None,
    resource_id: str | None,
) -> tuple[ServicePrincipal, str]:
    client_id = generate_client_id()
    client_secret = generate_client_secret()
    sp = ServicePrincipal(
        organization_id=organization_id,
        client_id=client_id,
        secret_hash=hash_secret(client_secret),
        name=name,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    db.add(sp)
    db.commit()
    db.refresh(sp)
    return sp, client_secret


def list_service_principals(db: Session, organization_id: uuid.UUID) -> list[ServicePrincipal]:
    stmt = select(ServicePrincipal).where(ServicePrincipal.organization_id == organization_id).order_by(
        ServicePrincipal.created_at.desc()
    )
    return list(db.execute(stmt).scalars().all())


def _get_or_404(db: Session, service_principal_id: uuid.UUID) -> ServicePrincipal:
    sp = db.get(ServicePrincipal, service_principal_id)
    if sp is None:
        raise NotFoundError("Service principal not found")
    return sp


def rotate_secret(db: Session, service_principal_id: uuid.UUID) -> str:
    sp = _get_or_404(db, service_principal_id)
    client_secret = generate_client_secret()
    sp.secret_hash = hash_secret(client_secret)
    db.commit()
    return client_secret


def revoke_service_principal(db: Session, service_principal_id: uuid.UUID) -> None:
    sp = _get_or_404(db, service_principal_id)
    sp.revoked_at = datetime.now(timezone.utc)
    db.commit()


def rename_service_principal(db: Session, service_principal_id: uuid.UUID, *, name: str) -> ServicePrincipal:
    """Rename only - never touches client_id/secret_hash/revoked_at."""
    sp = _get_or_404(db, service_principal_id)
    sp.name = name
    db.commit()
    db.refresh(sp)
    return sp
