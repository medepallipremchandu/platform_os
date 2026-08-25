import uuid

from app.core import permissions
from app.models.resume_analysis import ResumeAnalysis
from tests.conftest import auth_headers


def _make_resume(db_session, organization_id, resume_code):
    resume = ResumeAnalysis(
        organization_id=organization_id,
        resume_code=resume_code,
        original_filename="resume.pdf",
        file_type="pdf",
        raw_text="some text",
        candidate_name="Jon Doe",
        candidate_email="jon@old.example.com",
        candidate_phone="+15550001111",
        total_experience_years=3.0,
        summary="Old summary",
        skills=[],
        work_history=[],
        education=[],
        certifications=[],
        raw_llm_response={"raw": "unchanged"},
    )
    db_session.add(resume)
    db_session.commit()
    db_session.refresh(resume)
    return resume


def test_patch_resume_analysis_requires_applicants_write(client, db_session):
    org_id = uuid.uuid4()
    resume = _make_resume(db_session, org_id, "RESED1")

    headers = auth_headers(org_id=org_id, permissions=[permissions.APPLICANTS_READ])
    response = client.patch(
        f"/api/v1/resume-analysis/{resume.id}", json={"candidate_name": "Jonathan Doe"}, headers=headers
    )
    assert response.status_code == 403


def test_patch_resume_analysis_corrects_ocr_fields(client, db_session):
    org_id = uuid.uuid4()
    resume = _make_resume(db_session, org_id, "RESED2")

    headers = auth_headers(org_id=org_id, permissions=[permissions.APPLICANTS_WRITE], email="recruiter@example.com")
    response = client.patch(
        f"/api/v1/resume-analysis/{resume.id}",
        json={
            "candidate_name": "Jonathan Doe",
            "candidate_email": "jonathan@example.com",
            "candidate_phone": "+15550002222",
            "total_experience_years": 3.5,
            "summary": "New summary",
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["candidate_name"] == "Jonathan Doe"
    assert body["candidate_email"] == "jonathan@example.com"
    assert body["candidate_phone"] == "+15550002222"
    assert body["total_experience_years"] == 3.5
    assert body["summary"] == "New summary"
    assert body["modified_by"] == "recruiter@example.com"
    assert body["modified_at"] is not None
    # raw_text / raw_llm_response are not part of the response's editable surface at all - the
    # extraction inputs are untouched.
    assert "raw_llm_response" not in body

    read_headers = auth_headers(org_id=org_id, permissions=[permissions.APPLICANTS_READ])
    audit_response = client.get(f"/api/v1/resume-analysis/{resume.id}/audit-log", headers=read_headers)
    actions = [row["action"] for row in audit_response.json()]
    assert "updated" in actions


def test_patch_resume_analysis_partial_update_leaves_other_fields(client, db_session):
    org_id = uuid.uuid4()
    resume = _make_resume(db_session, org_id, "RESED3")

    headers = auth_headers(org_id=org_id, permissions=[permissions.APPLICANTS_WRITE])
    response = client.patch(
        f"/api/v1/resume-analysis/{resume.id}", json={"candidate_phone": "+15559998888"}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["candidate_phone"] == "+15559998888"
    assert body["candidate_name"] == "Jon Doe"
    assert body["candidate_email"] == "jon@old.example.com"


def test_patch_resume_analysis_from_other_org_is_404(client, db_session):
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    resume = _make_resume(db_session, org_b, "RESED4")

    headers = auth_headers(org_id=org_a, permissions=[permissions.APPLICANTS_WRITE])
    response = client.patch(
        f"/api/v1/resume-analysis/{resume.id}", json={"candidate_name": "x"}, headers=headers
    )
    assert response.status_code == 404
