import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit_log_entry import AuditLogEntry


def query_audit_events(
    db: Session,
    *,
    organization_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
    action: str | None,
    result: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    limit: int,
    offset: int,
) -> tuple[list[AuditLogEntry], int]:
    stmt = select(AuditLogEntry)
    count_stmt = select(func.count()).select_from(AuditLogEntry)

    if organization_id is not None:
        stmt = stmt.where(AuditLogEntry.organization_id == organization_id)
        count_stmt = count_stmt.where(AuditLogEntry.organization_id == organization_id)
    if actor_id is not None:
        stmt = stmt.where(AuditLogEntry.actor_id == actor_id)
        count_stmt = count_stmt.where(AuditLogEntry.actor_id == actor_id)
    if action is not None:
        stmt = stmt.where(AuditLogEntry.action == action)
        count_stmt = count_stmt.where(AuditLogEntry.action == action)
    if result is not None:
        stmt = stmt.where(AuditLogEntry.result == result)
        count_stmt = count_stmt.where(AuditLogEntry.result == result)
    if date_from is not None:
        stmt = stmt.where(AuditLogEntry.occurred_at >= date_from)
        count_stmt = count_stmt.where(AuditLogEntry.occurred_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(AuditLogEntry.occurred_at <= date_to)
        count_stmt = count_stmt.where(AuditLogEntry.occurred_at <= date_to)

    total = db.execute(count_stmt).scalar_one()
    stmt = stmt.order_by(AuditLogEntry.occurred_at.desc()).limit(limit).offset(offset)
    items = list(db.execute(stmt).scalars().all())
    return items, total
