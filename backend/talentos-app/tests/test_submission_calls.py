import uuid
from unittest.mock import AsyncMock

import pytest

from app.core import permissions
from app.models.jd_analysis import JDAnalysis
from app.models.resume_analysis import ResumeAnalysis
from app.models.submission import Submission
from app.models.voice_call import JDCallAgentConfig, SubmissionCall
from tests.conftest import auth_headers


def _make_jd(db_session, organization_id, jd_code):
    jd = JDAnalysis(
        organization_id=organization_id,
        jd_code=jd_code,
        jd_text="x" * 30,
        job_title="Engineer",
        responsibilities=[],
        qualifications=[],
        raw_llm_response={},
    )
    db_session.add(jd)
    db_session.commit()
    db_session.refresh(jd)
    return jd


def _make_resume(db_session, organization_id, resume_code, phone=None):
    resume = ResumeAnalysis(
        organization_id=organization_id,
        resume_code=resume_code,
        original_filename="resume.pdf",
        file_type="pdf",
        raw_text="some text",
        candidate_phone=phone,
        skills=[],
        work_history=[],
        education=[],
        certifications=[],
        raw_llm_response={},
    )
    db_session.add(resume)
    db_session.commit()
    db_session.refresh(resume)
    return resume


def _make_submission(db_session, organization_id, jd, resume, code):
    submission = Submission(
        organization_id=organization_id,
        submission_code=code,
        jd_analysis_id=jd.id,
        resume_analysis_id=resume.id,
    )
    db_session.add(submission)
    db_session.commit()
    db_session.refresh(submission)
    return submission


def _make_call_config(db_session, jd, call_agent_config_id="cac-1", enabled=True):
    config = JDCallAgentConfig(jd_analysis_id=jd.id, call_agent_config_id=call_agent_config_id, enabled=enabled)
    db_session.add(config)
    db_session.commit()
    return config


def test_trigger_call_without_config_is_409(client, db_session):
    org_id = uuid.uuid4()
    jd = _make_jd(db_session, org_id, "TSC01")
    resume = _make_resume(db_session, org_id, "RSC01", phone="+15550001111")
    submission = _make_submission(db_session, org_id, jd, resume, "SUBC01")

    headers = auth_headers(org_id=org_id, permissions=[permissions.SUBMISSIONS_WRITE])
    response = client.post(f"/api/v1/submissions/{submission.id}/calls", headers=headers)
    assert response.status_code == 409


def test_trigger_call_with_disabled_config_is_409(client, db_session):
    org_id = uuid.uuid4()
    jd = _make_jd(db_session, org_id, "TSC02")
    resume = _make_resume(db_session, org_id, "RSC02", phone="+15550001111")
    submission = _make_submission(db_session, org_id, jd, resume, "SUBC02")
    _make_call_config(db_session, jd, enabled=False)

    headers = auth_headers(org_id=org_id, permissions=[permissions.SUBMISSIONS_WRITE])
    response = client.post(f"/api/v1/submissions/{submission.id}/calls", headers=headers)
    assert response.status_code == 409


def test_trigger_call_without_candidate_phone_is_400(client, db_session):
    org_id = uuid.uuid4()
    jd = _make_jd(db_session, org_id, "TSC03")
    resume = _make_resume(db_session, org_id, "RSC03", phone=None)
    submission = _make_submission(db_session, org_id, jd, resume, "SUBC03")
    _make_call_config(db_session, jd)

    headers = auth_headers(org_id=org_id, permissions=[permissions.SUBMISSIONS_WRITE])
    response = client.post(f"/api/v1/submissions/{submission.id}/calls", headers=headers)
    assert response.status_code == 400


def test_trigger_call_success_creates_submission_call(client, db_session, monkeypatch):
    org_id = uuid.uuid4()
    jd = _make_jd(db_session, org_id, "TSC04")
    resume = _make_resume(db_session, org_id, "RSC04", phone="+15550001111")
    submission = _make_submission(db_session, org_id, jd, resume, "SUBC04")
    _make_call_config(db_session, jd, call_agent_config_id="cac-42")

    fake_create_call = AsyncMock(return_value={"id": "voice-call-abc", "status": "queued"})
    monkeypatch.setattr("app.services.voice_call_service.voice_agent_client.create_call", fake_create_call)

    headers = auth_headers(org_id=org_id, permissions=[permissions.SUBMISSIONS_WRITE], email="recruiter@example.com")
    response = client.post(f"/api/v1/submissions/{submission.id}/calls", headers=headers)
    assert response.status_code == 202
    body = response.json()
    assert body["voice_agent_call_id"] == "voice-call-abc"
    assert body["status"] == "queued"
    assert body["attempt_number"] == 1
    assert body["triggered_by"] == "recruiter@example.com"

    fake_create_call.assert_awaited_once()
    call_kwargs = fake_create_call.await_args.kwargs
    assert call_kwargs["call_agent_config_id"] == "cac-42"
    assert call_kwargs["to_number"] == "+15550001111"
    assert f"/webhooks/voice-agent/{body['id']}" in call_kwargs["webhook_url"]
    assert "secret=" in call_kwargs["webhook_url"]

    row = db_session.get(SubmissionCall, uuid.UUID(body["id"]))
    assert row is not None
    assert row.voice_agent_call_id == "voice-call-abc"


def test_second_call_attempt_increments_attempt_number(client, db_session, monkeypatch):
    org_id = uuid.uuid4()
    jd = _make_jd(db_session, org_id, "TSC05")
    resume = _make_resume(db_session, org_id, "RSC05", phone="+15550001111")
    submission = _make_submission(db_session, org_id, jd, resume, "SUBC05")
    _make_call_config(db_session, jd)

    fake_create_call = AsyncMock(return_value={"id": "voice-call-1", "status": "queued"})
    monkeypatch.setattr("app.services.voice_call_service.voice_agent_client.create_call", fake_create_call)

    headers = auth_headers(org_id=org_id, permissions=[permissions.SUBMISSIONS_WRITE])
    first = client.post(f"/api/v1/submissions/{submission.id}/calls", headers=headers)
    assert first.json()["attempt_number"] == 1

    fake_create_call.return_value = {"id": "voice-call-2", "status": "queued"}
    second = client.post(f"/api/v1/submissions/{submission.id}/calls", headers=headers)
    assert second.json()["attempt_number"] == 2


def test_list_calls_lazily_refreshes_non_terminal_status(client, db_session, monkeypatch):
    org_id = uuid.uuid4()
    jd = _make_jd(db_session, org_id, "TSC06")
    resume = _make_resume(db_session, org_id, "RSC06", phone="+15550001111")
    submission = _make_submission(db_session, org_id, jd, resume, "SUBC06")

    call = SubmissionCall(submission_id=submission.id, voice_agent_call_id="voice-call-x", status="dialing", attempt_number=1)
    db_session.add(call)
    db_session.commit()

    fake_get_call = AsyncMock(return_value={"status": "completed", "end_reason": "hangup"})
    fake_get_summary = AsyncMock(return_value={"summary_text": "Great candidate", "extracted_fields": {"years": 4}})
    monkeypatch.setattr("app.services.voice_call_service.voice_agent_client.get_call", fake_get_call)
    monkeypatch.setattr("app.services.voice_call_service.voice_agent_client.get_summary", fake_get_summary)

    headers = auth_headers(org_id=org_id, permissions=[permissions.SUBMISSIONS_READ])
    response = client.get(f"/api/v1/submissions/{submission.id}/calls", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["status"] == "completed"
    assert body[0]["end_reason"] == "hangup"
    assert body[0]["summary_text"] == "Great candidate"
    assert body[0]["extracted_fields"] == {"years": 4}


def test_list_calls_does_not_refetch_terminal_calls(client, db_session, monkeypatch):
    org_id = uuid.uuid4()
    jd = _make_jd(db_session, org_id, "TSC07")
    resume = _make_resume(db_session, org_id, "RSC07", phone="+15550001111")
    submission = _make_submission(db_session, org_id, jd, resume, "SUBC07")

    call = SubmissionCall(submission_id=submission.id, voice_agent_call_id="voice-call-y", status="completed", attempt_number=1)
    db_session.add(call)
    db_session.commit()

    fake_get_call = AsyncMock()
    monkeypatch.setattr("app.services.voice_call_service.voice_agent_client.get_call", fake_get_call)

    headers = auth_headers(org_id=org_id, permissions=[permissions.SUBMISSIONS_READ])
    response = client.get(f"/api/v1/submissions/{submission.id}/calls", headers=headers)
    assert response.status_code == 200
    fake_get_call.assert_not_awaited()


def test_conversation_endpoint_proxies_live_transcript(client, db_session, monkeypatch):
    org_id = uuid.uuid4()
    jd = _make_jd(db_session, org_id, "TSC08")
    resume = _make_resume(db_session, org_id, "RSC08", phone="+15550001111")
    submission = _make_submission(db_session, org_id, jd, resume, "SUBC08")
    call = SubmissionCall(submission_id=submission.id, voice_agent_call_id="voice-call-z", status="connected", attempt_number=1)
    db_session.add(call)
    db_session.commit()
    db_session.refresh(call)

    fake_conversation = AsyncMock(
        return_value=[
            {"id": "t1", "turn_index": 0, "speaker": "ai", "text": "Hi, is this Jane?", "created_at": "2026-08-25T00:00:00Z"}
        ]
    )
    monkeypatch.setattr("app.api.v1.submissions.voice_agent_client.get_conversation", fake_conversation)

    headers = auth_headers(org_id=org_id, permissions=[permissions.SUBMISSIONS_READ])
    response = client.get(f"/api/v1/submissions/{submission.id}/calls/{call.id}/conversation", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body[0]["speaker"] == "ai"
    fake_conversation.assert_awaited_once_with("voice-call-z")


def test_conversation_for_unknown_call_id_is_404(client, db_session):
    org_id = uuid.uuid4()
    jd = _make_jd(db_session, org_id, "TSC09")
    resume = _make_resume(db_session, org_id, "RSC09", phone="+15550001111")
    submission = _make_submission(db_session, org_id, jd, resume, "SUBC09")

    headers = auth_headers(org_id=org_id, permissions=[permissions.SUBMISSIONS_READ])
    response = client.get(f"/api/v1/submissions/{submission.id}/calls/{uuid.uuid4()}/conversation", headers=headers)
    assert response.status_code == 404


def test_trigger_call_missing_token_is_401(client):
    response = client.post(f"/api/v1/submissions/{uuid.uuid4()}/calls")
    assert response.status_code == 401


def test_trigger_call_wrong_permission_is_403(client, db_session):
    org_id = uuid.uuid4()
    jd = _make_jd(db_session, org_id, "TSC10")
    resume = _make_resume(db_session, org_id, "RSC10", phone="+15550001111")
    submission = _make_submission(db_session, org_id, jd, resume, "SUBC10")

    headers = auth_headers(org_id=org_id, permissions=[permissions.SUBMISSIONS_READ])  # read, not write
    response = client.post(f"/api/v1/submissions/{submission.id}/calls", headers=headers)
    assert response.status_code == 403
