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


# --- Deep child chains -----------------------------------------------------------------------
#
# Everything above covers entities that carry organization_id themselves. These cover the ones
# that DON'T: skills, questions, interview_sessions and evaluations have no organization_id
# column, and are isolated purely by the service layer joining back to a scoped root
# (JDAnalysis or Submission). That makes their isolation a property of query construction rather
# than of the schema, so it can be broken by an innocuous-looking refactor without any constraint
# firing. These tests are the thing that would notice.
#
# Evaluation is the deepest: Evaluation -> Question -> Skill -> JDAnalysis, a three-hop join back
# to the only row that knows which tenant it belongs to.


def _make_resume(db_session, organization_id, resume_code):
    resume = ResumeAnalysis(
        organization_id=organization_id,
        resume_code=resume_code,
        original_filename="cv.pdf",
        file_type="pdf",
        raw_text="x" * 30,
    )
    db_session.add(resume)
    db_session.commit()
    db_session.refresh(resume)
    return resume


def _make_submission(db_session, organization_id, submission_code):
    jd = _make_jd(db_session, organization_id, submission_code + "J")
    resume = _make_resume(db_session, organization_id, submission_code + "R")
    submission = Submission(
        organization_id=organization_id,
        submission_code=submission_code,
        jd_analysis_id=jd.id,
        resume_analysis_id=resume.id,
    )
    db_session.add(submission)
    db_session.commit()
    db_session.refresh(submission)
    return submission


def _make_skill(db_session, jd_analysis_id, name="Python"):
    from app.models.jd_analysis import Skill

    skill = Skill(jd_analysis_id=jd_analysis_id, name=name)
    db_session.add(skill)
    db_session.commit()
    db_session.refresh(skill)
    return skill


def _make_question(db_session, skill_id):
    from app.models.question import Question

    question = Question(
        skill_id=skill_id, question_type="descriptive", question_text="Explain the GIL.", difficulty="medium"
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    return question


def _make_interview_session(db_session, submission_id):
    from app.models.interview_session import InterviewSession

    session = InterviewSession(submission_id=submission_id)
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


def _make_evaluation(db_session, question_id):
    from app.models.evaluation import Evaluation

    evaluation = Evaluation(question_id=question_id, overall_score_percentage=75)
    db_session.add(evaluation)
    db_session.commit()
    db_session.refresh(evaluation)
    return evaluation


def test_questions_for_a_skill_in_another_org_are_404(client, db_session):
    """Skill -> JDAnalysis. The skill id is a real, existing id - it just belongs to org B."""
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    jd_b = _make_jd(db_session, org_b, "TOSSK")
    skill_b = _make_skill(db_session, jd_b.id)
    _make_question(db_session, skill_b.id)

    headers = auth_headers(org_id=org_a, permissions=[permissions.INTERVIEWS_READ])
    response = client.get(f"/api/v1/questions/{skill_b.id}", headers=headers)
    assert response.status_code == 404


def test_an_interview_session_in_another_org_is_404(client, db_session):
    """InterviewSession -> Submission."""
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    submission_b = _make_submission(db_session, org_b, "TOSIS")
    session_b = _make_interview_session(db_session, submission_b.id)

    headers = auth_headers(org_id=org_a, permissions=[permissions.INTERVIEWS_READ])
    assert client.get(f"/api/v1/interview-sessions/{session_b.id}", headers=headers).status_code == 404


def test_listing_interview_sessions_never_crosses_orgs(client, db_session):
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    session_a = _make_interview_session(db_session, _make_submission(db_session, org_a, "TOSLA").id)
    _make_interview_session(db_session, _make_submission(db_session, org_b, "TOSLB").id)

    headers = auth_headers(org_id=org_a, permissions=[permissions.INTERVIEWS_READ])
    response = client.get("/api/v1/interview-sessions", headers=headers)
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [str(session_a.id)]


def test_an_evaluation_in_another_org_is_404(client, db_session):
    """The deepest chain: Evaluation -> Question -> Skill -> JDAnalysis."""
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    jd_b = _make_jd(db_session, org_b, "TOSEV")
    evaluation_b = _make_evaluation(db_session, _make_question(db_session, _make_skill(db_session, jd_b.id).id).id)

    headers = auth_headers(org_id=org_a, permissions=[permissions.INTERVIEWS_READ])
    assert client.get(f"/api/v1/evaluations/{evaluation_b.id}", headers=headers).status_code == 404


def test_the_owning_org_can_still_read_its_own_deep_children(client, db_session):
    """The other half of every isolation test: proving the filter rejects the wrong tenant is
    worthless without proving it still admits the right one."""
    org_a = uuid.uuid4()
    jd_a = _make_jd(db_session, org_a, "TOSOK")
    skill_a = _make_skill(db_session, jd_a.id)
    _make_question(db_session, skill_a.id)
    session_a = _make_interview_session(db_session, _make_submission(db_session, org_a, "TOSOS").id)

    headers = auth_headers(org_id=org_a, permissions=[permissions.INTERVIEWS_READ])
    assert client.get(f"/api/v1/questions/{skill_a.id}", headers=headers).status_code == 200
    assert client.get(f"/api/v1/interview-sessions/{session_a.id}", headers=headers).status_code == 200
