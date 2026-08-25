"""Background retry orchestration. A simple asyncio loop started in main.py's lifespan, polling
every settings.RETRY_POLL_INTERVAL_SECONDS for calls whose next_retry_at is due, and placing a
brand-new Call row for each (same to_number/call_script/telephony_provider_config_id/
call_agent_config_id/webhook_url/metadata, attempt_number+1, root_call_id pointing at the first
attempt) - dialed through the telephony provider exactly like a fresh call.

`run_once` is exposed separately from `poll_forever` so tests can drive exactly one poll pass
against a Session with next_retry_at manipulated directly, with no real event loop or Twilio
call involved (place_call is still awaited, so tests should stub/monkeypatch
app.providers.telephony.get_telephony_provider or app.services.calls_service.dial).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_credentials
from app.core.state_machine import CallStatus
from app.database import SessionLocal
from app.models.call import Call
from app.services import calls_service, providers_service

logger = logging.getLogger("app.services.retry_poller")


def _successor_exists(db: Session, call: Call) -> bool:
    """A successor is a call whose root_call_id (or own id, if it's attempt 1) equals this
    call's root, with attempt_number one higher. Since only the root (attempt 1) ever has
    root_call_id == None, `call.root_call_id or call.id` always yields the shared root id."""
    root_id = call.root_call_id or call.id
    result = db.execute(
        select(Call.id).where(Call.root_call_id == root_id, Call.attempt_number == call.attempt_number + 1)
    )
    return result.first() is not None


async def _fire_retry(db: Session, call: Call) -> Call | None:
    if _successor_exists(db, call):
        # Already handled by a previous poll pass (or a race) - just clear the stale marker.
        call.next_retry_at = None
        db.commit()
        return None

    root_id = call.root_call_id or call.id
    provider_config = providers_service.get_provider_for_call(
        db, call.organization_id, call.telephony_provider_config_id
    )
    provider_creds = decrypt_credentials(provider_config.encrypted_credentials)

    successor = Call(
        organization_id=call.organization_id,
        call_agent_config_id=call.call_agent_config_id,
        telephony_provider_config_id=call.telephony_provider_config_id,
        to_number=call.to_number,
        from_number=call.from_number,
        status=CallStatus.CREATED.value,
        max_duration_minutes=call.max_duration_minutes,
        call_script=call.call_script,
        webhook_url=call.webhook_url,
        metadata_json=call.metadata_json,
        retry_max_attempts=call.retry_max_attempts,
        retry_interval_minutes=call.retry_interval_minutes,
        retry_on_statuses=call.retry_on_statuses,
        attempt_number=call.attempt_number + 1,
        root_call_id=root_id,
        created_by=call.created_by,
    )
    db.add(successor)
    db.flush()
    calls_service.log_event(
        db, successor, "CALL_CREATED", {"to_number": successor.to_number, "retry_of": str(call.id)}
    )
    calls_service.transition(db, successor, CallStatus.QUEUED, "CALL_QUEUED")
    db.commit()

    await calls_service.dial(db, successor, provider_config.provider, provider_creds)

    # Clear the original row's next_retry_at now that the retry has actually fired, so the
    # poller never re-fires it.
    call.next_retry_at = None
    db.commit()
    db.refresh(successor)
    return successor


async def run_once(db: Session) -> list[Call]:
    """Finds calls with next_retry_at <= now() and no successor call yet, places a brand-new
    Call for each, and clears next_retry_at on the original. Returns the newly-created successor
    Call rows (empty list if none were due)."""
    now = datetime.now(timezone.utc)
    due = list(
        db.execute(select(Call).where(Call.next_retry_at.isnot(None), Call.next_retry_at <= now)).scalars().all()
    )

    created: list[Call] = []
    for call in due:
        successor = await _fire_retry(db, call)
        if successor is not None:
            created.append(successor)
    return created


async def poll_forever(interval_seconds: int) -> None:
    """Started as a background asyncio task from main.py's lifespan; runs until cancelled at
    shutdown."""
    while True:
        try:
            db = SessionLocal()
            try:
                created = await run_once(db)
                if created:
                    logger.info(
                        "Retry poller placed %d follow-up call(s): %s",
                        len(created),
                        [str(c.id) for c in created],
                    )
            finally:
                db.close()
        except Exception:
            logger.exception("Retry poller iteration failed")
        await asyncio.sleep(interval_seconds)
