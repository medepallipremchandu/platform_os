import uuid

from app.core import permissions
from app.models.jd_analysis import JDAnalysis
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


def test_get_call_config_is_null_before_any_config_is_set(client, db_session):
    org_id = uuid.uuid4()
    jd = _make_jd(db_session, org_id, "TOSCC1")

    headers = auth_headers(org_id=org_id, permissions=[permissions.REQUIREMENTS_READ])
    response = client.get(f"/api/v1/jd-analysis/{jd.id}/call-config", headers=headers)
    assert response.status_code == 200
    assert response.json() is None


def test_put_then_get_call_config_roundtrips(client, db_session):
    org_id = uuid.uuid4()
    jd = _make_jd(db_session, org_id, "TOSCC2")

    write_headers = auth_headers(org_id=org_id, permissions=[permissions.REQUIREMENTS_WRITE], email="recruiter@example.com")
    put_response = client.put(
        f"/api/v1/jd-analysis/{jd.id}/call-config",
        json={"call_agent_config_id": "cac-123", "enabled": True},
        headers=write_headers,
    )
    assert put_response.status_code == 200
    assert put_response.json() == {"call_agent_config_id": "cac-123", "enabled": True}

    read_headers = auth_headers(org_id=org_id, permissions=[permissions.REQUIREMENTS_READ])
    get_response = client.get(f"/api/v1/jd-analysis/{jd.id}/call-config", headers=read_headers)
    assert get_response.status_code == 200
    assert get_response.json() == {"call_agent_config_id": "cac-123", "enabled": True}


def test_put_call_config_upserts_not_duplicates(client, db_session):
    org_id = uuid.uuid4()
    jd = _make_jd(db_session, org_id, "TOSCC3")
    headers = auth_headers(org_id=org_id, permissions=[permissions.REQUIREMENTS_WRITE])

    client.put(f"/api/v1/jd-analysis/{jd.id}/call-config", json={"call_agent_config_id": "cac-1", "enabled": True}, headers=headers)
    second = client.put(
        f"/api/v1/jd-analysis/{jd.id}/call-config", json={"call_agent_config_id": "cac-2", "enabled": False}, headers=headers
    )
    assert second.status_code == 200
    assert second.json() == {"call_agent_config_id": "cac-2", "enabled": False}

    from app.models.voice_call import JDCallAgentConfig

    rows = db_session.query(JDCallAgentConfig).filter(JDCallAgentConfig.jd_analysis_id == jd.id).all()
    assert len(rows) == 1


def test_call_config_requires_requirements_read_permission(client, db_session):
    org_id = uuid.uuid4()
    jd = _make_jd(db_session, org_id, "TOSCC4")
    headers = auth_headers(org_id=org_id, permissions=[permissions.SUBMISSIONS_READ])  # wrong permission
    response = client.get(f"/api/v1/jd-analysis/{jd.id}/call-config", headers=headers)
    assert response.status_code == 403


def test_call_config_from_other_org_jd_is_404(client, db_session):
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    jd_b = _make_jd(db_session, org_b, "TOSCC5")
    headers = auth_headers(org_id=org_a, permissions=[permissions.REQUIREMENTS_READ])
    response = client.get(f"/api/v1/jd-analysis/{jd_b.id}/call-config", headers=headers)
    assert response.status_code == 404


def test_call_config_missing_token_is_401(client):
    response = client.get(f"/api/v1/jd-analysis/{uuid.uuid4()}/call-config")
    assert response.status_code == 401
