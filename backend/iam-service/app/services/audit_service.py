"""iam-service's own audit trail - the same AuditLogEntry table that iam-console reads via
GET /audit/events, and that /audit/events (POST) lets other services write into. iam-service
writes into it directly for its own authn/authz events (login, lockout, refresh, permission
denials on its own endpoints) rather than going through its own HTTP endpoint."""
import uuid

from sqlalchemy.orm import Session

from app.models.audit_log_entry import AuditLogEntry


def record_audit_event(
    db: Session,
    *,
    organization_id: uuid.UUID | None,
    actor_type: str,
    actor_id: uuid.UUID | None,
    action: str,
    target_type: str,
    target_id: str | None = None,
    result: str,
    correlation_id: str | None = None,
    source_ip: str | None = None,
    user_agent: str | None = None,
    changes: dict | None = None,
) -> AuditLogEntry:
    entry = AuditLogEntry(
        organization_id=organization_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        result=result,
        correlation_id=correlation_id,
        source_ip=source_ip,
        user_agent=user_agent,
        changes=changes,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
