"""Verifies the retry-scheduling background loop (app/services/retry_poller.py) without ever
calling Twilio: next_retry_at is manipulated directly on a Call row constructed straight against
the DB, `run_once` is driven directly (no real event loop / background task needed), and the
telephony provider is stubbed out with a fake that "succeeds" instantly.
"""
import uuid
from datetime import datetime, timedelta, timezone

from app.core.state_machine import CallStatus
from app.models.call import Call
from app.services import retry_poller
from app.services.calls_service import transition
from tests.test_calls import _fake_get_telephony_provider
from tests.test_providers import _create_provider


def _base_call(**overrides) -> Call:
    defaults = dict(
        organization_id=uuid.uuid4(),
        telephony_provider_config_id=uuid.uuid4(),
        to_number="+15551234567",
        from_number="+15550001111",
        status=CallStatus.NO_ANSWER.value,
        max_duration_minutes=5,
        call_script={"persona": "You are Ava.", "objective": "Confirm.", "consent_line": "c", "closing_line": "Bye.", "fields": []},
        metadata_json={},
        retry_max_attempts=2,
        retry_interval_minutes=15,
        retry_on_statuses=["NO_ANSWER", "BUSY"],
        attempt_number=1,
        created_by="tester@example.com",
    )
    defaults.update(overrides)
    return Call(**defaults)


async def test_poller_creates_followup_call_for_due_retry(client, db_session, monkeypatch):
    monkeypatch.setattr("app.services.calls_service.get_telephony_provider", _fake_get_telephony_provider)

    org_id = uuid.uuid4()
    provider_response = _create_provider(client, org_id)
    provider_id = uuid.UUID(provider_response.json()["id"])

    original = _base_call(
        organization_id=org_id,
        telephony_provider_config_id=provider_id,
        next_retry_at=datetime.now(timezone.utc) - timedelta(minutes=1),  # already due
    )
    db_session.add(original)
    db_session.commit()
    db_session.refresh(original)

    created = await retry_poller.run_once(db_session)

    assert len(created) == 1
    successor = created[0]
    assert successor.attempt_number == 2
    assert successor.root_call_id == original.id
    assert successor.to_number == original.to_number
    assert successor.call_agent_config_id == original.call_agent_config_id
    assert successor.telephony_provider_config_id == original.telephony_provider_config_id
    assert successor.status == CallStatus.DIALING.value  # fake provider "succeeds"

    db_session.refresh(original)
    assert original.next_retry_at is None  # cleared once the retry has fired


async def test_poller_ignores_calls_not_yet_due(client, db_session, monkeypatch):
    monkeypatch.setattr("app.services.calls_service.get_telephony_provider", _fake_get_telephony_provider)

    org_id = uuid.uuid4()
    provider_id = uuid.UUID(_create_provider(client, org_id).json()["id"])

    not_yet_due = _base_call(
        organization_id=org_id,
        telephony_provider_config_id=provider_id,
        next_retry_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    db_session.add(not_yet_due)
    db_session.commit()

    created = await retry_poller.run_once(db_session)
    assert created == []


async def test_poller_does_not_refire_if_successor_already_exists(client, db_session):
    org_id = uuid.uuid4()
    provider_id = uuid.UUID(_create_provider(client, org_id).json()["id"])

    root = _base_call(
        organization_id=org_id,
        telephony_provider_config_id=provider_id,
        next_retry_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(root)
    db_session.commit()
    db_session.refresh(root)

    successor = _base_call(
        organization_id=org_id,
        telephony_provider_config_id=provider_id,
        status=CallStatus.QUEUED.value,
        attempt_number=2,
        root_call_id=root.id,
    )
    db_session.add(successor)
    db_session.commit()

    created = await retry_poller.run_once(db_session)
    assert created == []

    db_session.refresh(root)
    assert root.next_retry_at is None  # cleared even though no new call was placed (already handled)


def test_transition_schedules_retry_when_within_attempt_budget(client, db_session):
    provider_id = uuid.UUID(_create_provider(client, uuid.uuid4()).json()["id"])
    call = _base_call(
        telephony_provider_config_id=provider_id,
        status=CallStatus.RINGING.value,
        retry_max_attempts=2,
        attempt_number=1,
        next_retry_at=None,
    )
    db_session.add(call)
    db_session.commit()

    transition(db_session, call, CallStatus.NO_ANSWER, "CALL_NO_ANSWER")
    db_session.commit()

    assert call.status == CallStatus.NO_ANSWER.value
    assert call.next_retry_at is not None
    expected = datetime.now(timezone.utc) + timedelta(minutes=call.retry_interval_minutes)
    assert abs((call.next_retry_at - expected).total_seconds()) < 5


def test_transition_does_not_schedule_retry_once_budget_exhausted(client, db_session):
    provider_id = uuid.UUID(_create_provider(client, uuid.uuid4()).json()["id"])
    call = _base_call(
        telephony_provider_config_id=provider_id,
        status=CallStatus.RINGING.value,
        retry_max_attempts=1,
        attempt_number=1,
        next_retry_at=None,
    )
    db_session.add(call)
    db_session.commit()

    transition(db_session, call, CallStatus.NO_ANSWER, "CALL_NO_ANSWER")
    db_session.commit()

    assert call.next_retry_at is None  # attempt_number(1) is not < retry_max_attempts(1)


def test_transition_does_not_schedule_retry_for_non_retryable_status(client, db_session):
    provider_id = uuid.UUID(_create_provider(client, uuid.uuid4()).json()["id"])
    call = _base_call(
        telephony_provider_config_id=provider_id,
        status=CallStatus.CONVERSATION.value,
        retry_max_attempts=3,
        retry_on_statuses=["NO_ANSWER", "BUSY"],
        next_retry_at=None,
    )
    db_session.add(call)
    db_session.commit()

    transition(db_session, call, CallStatus.DISCONNECTED, "CALL_DISCONNECTED")
    db_session.commit()

    assert call.next_retry_at is None  # DISCONNECTED isn't in this call's retry_on_statuses
