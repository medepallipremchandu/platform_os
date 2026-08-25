import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import CurrentActor, current_actor, get_db, require_permission
from app.schemas.audit import AuditEventCreateRequest, AuditLogEntryOut, AuditLogPage
from app.services.audit_query_service import query_audit_events
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/audit", tags=["audit"])


@router.post("/events", response_model=AuditLogEntryOut, status_code=201)
def create_audit_event(
    payload: AuditEventCreateRequest,
    request: Request,
    actor: CurrentActor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    # organization_id/actor_* are derived server-side from the caller's own verified token,
    # never trusted from the request body - otherwise a caller could stamp another org's
    # audit log (design doc §8 / task spec).
    entry = record_audit_event(
        db,
        organization_id=actor.org_id,
        actor_type=actor.principal_type,
        actor_id=actor.id,
        action=payload.action,
        target_type=payload.target_type,
        target_id=payload.target_id,
        result=payload.result,
        correlation_id=payload.correlation_id,
        source_ip=payload.source_ip or (request.client.host if request.client else None),
        user_agent=payload.user_agent or request.headers.get("user-agent"),
        changes=payload.changes,
    )
    return entry


@router.get("/events", response_model=AuditLogPage)
def list_audit_events(
    organization_id: uuid.UUID | None = Query(default=None),
    actor_id: uuid.UUID | None = Query(default=None),
    action: str | None = Query(default=None),
    result: str | None = Query(default=None, pattern="^(success|denied|error)$"),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _actor: CurrentActor = Depends(require_permission("talentos.iam.audit.read")),
):
    items, total = query_audit_events(
        db,
        organization_id=organization_id,
        actor_id=actor_id,
        action=action,
        result=result,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return AuditLogPage(items=items, total=total, limit=limit, offset=offset)
