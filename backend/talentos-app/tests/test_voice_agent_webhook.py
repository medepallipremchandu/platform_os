"""The webhook receiver (app/api/webhooks.py) has no IAM bearer-token auth - it's called by
voice-agent-service, not an interactive user - so its only gate is the `?secret=` query param.
These tests exercise that gate plus the "always re-fetch from voice-agent-service, never trust
the payload" behavior."""
import uuid
from unittest.mock import AsyncMock

from app.config import get_settings
from app.models.jd_analysis import JDAnalysis
from app.models.resume_analysis import ResumeAnalysis
from app.models.submission import Submission
from app.models.voice_call import SubmissionCall


def _make_submission_call(db_session, status="dialing"):
    org_id = uuid.uuid4()
    jd = JDAnalysis(
        organization_id=org_id,
        jd_code=f"TWH{uuid.uuid4().hex[:4].upper()}",
        jd_text="x" * 30,
        responsibilities=[],
        qualifications=[],
        raw_llm_response={},
    )
    resume = ResumeAnalysis(
        organization_id=org_id,
        resume_code=f"RWH{uuid.uuid4().hex[:4].upper()}",
        original_filename="r.pdf",
        file_type="pdf",
        raw_text="text",
        candidate_phone="+15550001111",
        skills=[],
        work_history=[],
        education=[],
        certifications=[],
        raw_llm_response={},
    )
    db_session.add_all([jd, resume])
    db_session.commit()
    submission = Submission(organization_id=org_id, submission_code=f"SWH{uuid.uuid4().hex[:4].upper()}", jd_analysis_id=jd.id, resume_analysis_id=resume.id)
    db_session.add(submission)
    db_session.commit()

    call = SubmissionCall(submission_id=submission.id, voice_agent_call_id="voice-call-webhook", status=status, attempt_number=1)
    db_session.add(call)
    db_session.commit()
    db_session.refresh(call)
    return call


def test_webhook_missing_secret_is_401(client, db_session):
    call = _make_submission_call(db_session)
    response = client.post(f"/webhooks/voice-agent/{call.id}")
    assert response.status_code == 401


def test_webhook_wrong_secret_is_401(client, db_session):
    call = _make_submission_call(db_session)
    response = client.post(f"/webhooks/voice-agent/{call.id}?secret=wrong")
    assert response.status_code == 401


def test_webhook_correct_secret_updates_cached_row_from_live_refetch(client, db_session, monkeypatch):
    call = _make_submission_call(db_session, status="dialing")
    secret = get_settings().VOICE_AGENT_WEBHOOK_SECRET
    assert secret, "VOICE_AGENT_WEBHOOK_SECRET must be set for this test to be meaningful"

    fake_get_call = AsyncMock(return_value={"status": "completed", "end_reason": "hangup"})
    fake_get_summary = AsyncMock(return_value={"summary_text": "Solid candidate", "extracted_fields": {"years": 6}})
    monkeypatch.setattr("app.services.voice_call_service.voice_agent_client.get_call", fake_get_call)
    monkeypatch.setattr("app.services.voice_call_service.voice_agent_client.get_summary", fake_get_summary)

    # The webhook's own payload claims a status - the handler must NOT trust it and must
    # re-fetch from voice-agent-service instead (fake_get_call above returns "completed"
    # regardless of what's posted here).
    response = client.post(
        f"/webhooks/voice-agent/{call.id}?secret={secret}",
        json={"event_type": "call.status_changed", "call_id": "voice-call-webhook", "status": "ringing", "payload": {}},
    )
    assert response.status_code == 204

    db_session.expire_all()
    refreshed = db_session.get(SubmissionCall, call.id)
    assert refreshed.status == "completed"
    assert refreshed.end_reason == "hangup"
    assert refreshed.summary_text == "Solid candidate"
    assert refreshed.extracted_fields == {"years": 6}
    fake_get_call.assert_awaited_once_with("voice-call-webhook")
    fake_get_summary.assert_awaited_once_with("voice-call-webhook")


def test_webhook_for_unknown_submission_call_id_still_204s(client):
    secret = get_settings().VOICE_AGENT_WEBHOOK_SECRET
    # Right secret, but no such SubmissionCall row - acked quietly rather than 404ing (this is a
    # best-effort sender, not worth it retry-storming).
    response = client.post(f"/webhooks/voice-agent/{uuid.uuid4()}?secret={secret}")
    assert response.status_code == 204


def test_webhook_non_terminal_status_does_not_fetch_summary(client, db_session, monkeypatch):
    call = _make_submission_call(db_session, status="dialing")
    secret = get_settings().VOICE_AGENT_WEBHOOK_SECRET

    fake_get_call = AsyncMock(return_value={"status": "connected", "end_reason": None})
    fake_get_summary = AsyncMock()
    monkeypatch.setattr("app.services.voice_call_service.voice_agent_client.get_call", fake_get_call)
    monkeypatch.setattr("app.services.voice_call_service.voice_agent_client.get_summary", fake_get_summary)

    response = client.post(f"/webhooks/voice-agent/{call.id}?secret={secret}", json={})
    assert response.status_code == 204
    fake_get_summary.assert_not_awaited()

    db_session.expire_all()
    refreshed = db_session.get(SubmissionCall, call.id)
    assert refreshed.status == "connected"
