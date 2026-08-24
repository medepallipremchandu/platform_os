import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def record_audit(
    db: Session,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    changed_by: str,
    changes: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            changed_by=changed_by,
            changes=changes,
        )
    )


def get_audit_log(db: Session, entity_type: str, entity_id: uuid.UUID) -> list[AuditLog]:
    stmt = (
        select(AuditLog)
        .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
        .order_by(AuditLog.changed_at)
    )
    return list(db.execute(stmt).scalars().all())
