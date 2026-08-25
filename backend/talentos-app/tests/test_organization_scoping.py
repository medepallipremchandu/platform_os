import uuid

from app.core import permissions
from app.models.jd_analysis import JDAnalysis
from app.models.resume_analysis import ResumeAnalysis
from app.models.submission import Submission
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


def test_list_jd_analyses_only_returns_caller_org(client, db_session):
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    jd_a = _make_jd(db_session, org_a, "TOSAA")
    _make_jd(db_session, org_b, "TOSBB")

    headers = auth_headers(org_id=org_a, permissions=[permissions.REQUIREMENTS_READ])
    response = client.get("/api/v1/jd-analysis", headers=headers)
    assert response.status_code == 200
    codes = [row["jd_code"] for row in response.json()]
    assert codes == [jd_a.jd_code]


def test_get_jd_analysis_from_other_org_is_404(client, db_session):
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    jd_b = _make_jd(db_session, org_b, "TOSCC")

    headers = auth_headers(org_id=org_a, permissions=[permissions.REQUIREMENTS_READ])
    response = client.get(f"/api/v1/jd-analysis/{jd_b.id}", headers=headers)
    assert response.status_code == 404


def test_create_jd_analysis_sets_organization_id_from_token_not_body(client, monkeypatch):
    org_id = uuid.uuid4()

    async def fake_invoke(agent_name, variables):
        return {
            "job_title": "Backend Engineer",
            "role_context": "Platform team",
            "job_context_summary": "Build APIs",
            "responsibilities": ["Ship features"],
            "qualifications": ["3+ years Python"],
            "skills": [],
        }

    monkeypatch.setattr("app.services.jd_analysis_service.agent_client.invoke", fake_invoke)

    headers = auth_headers(
        org_id=org_id, permissions=[permissions.REQUIREMENTS_WRITE], email="creator@example.com"
    )
    response = client.post("/api/v1/jd-analysis", json={"jd_text": "x" * 30}, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["created_by"] == "creator@example.com"

    # Confirm the organization_id actually stamped on the row matches the token's org, by
    # listing with a token scoped to that same org.
    list_headers = auth_headers(org_id=org_id, permissions=[permissions.REQUIREMENTS_READ])
    list_response = client.get("/api/v1/jd-analysis", headers=list_headers)
    assert any(row["id"] == body["id"] for row in list_response.json())

    other_org_headers = auth_headers(org_id=uuid.uuid4(), permissions=[permissions.REQUIREMENTS_READ])
    other_org_response = client.get("/api/v1/jd-analysis", headers=other_org_headers)
    assert other_org_response.json() == []


def _make_resume(db_session, organization_id, resume_code):
    resume = ResumeAnalysis(
        organization_id=organization_id,
        resume_code=resume_code,
        original_filename="resume.pdf",
        file_type="pdf",
        raw_text="some text",
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


def test_submission_create_rejects_cross_org_references(client, db_session):
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    jd_a = _make_jd(db_session, org_a, "TOSDD")
    resume_b = _make_resume(db_session, org_b, "RESAA")

    headers = auth_headers(org_id=org_a, permissions=[permissions.SUBMISSIONS_WRITE])
    response = client.post(
        "/api/v1/submissions",
        json={"jd_analysis_id": str(jd_a.id), "resume_analysis_id": str(resume_b.id)},
        headers=headers,
    )
    # resume_b belongs to org_b - must not be visible/usable from org_a's token
    assert response.status_code == 404
