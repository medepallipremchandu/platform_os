import uuid

from app.core import permissions
from app.models.jd_analysis import JDAnalysis, Rubric, Skill
from tests.conftest import auth_headers


def _make_jd_with_skill(db_session, organization_id, jd_code, rubric_weights=(60, 40)):
    jd = JDAnalysis(
        organization_id=organization_id,
        jd_code=jd_code,
        jd_text="x" * 30,
        job_title="Engineer",
        responsibilities=[],
        qualifications=[],
        raw_llm_response={},
    )
    skill = Skill(name="Python", description="General Python proficiency")
    for i, weight in enumerate(rubric_weights):
        skill.rubrics.append(Rubric(name=f"Rubric {i}", description="desc", weight_percentage=weight))
    jd.skills.append(skill)
    db_session.add(jd)
    db_session.commit()
    db_session.refresh(jd)
    return jd, jd.skills[0], jd.skills[0].rubrics


def test_patch_skill_requires_requirements_write(client, db_session):
    org_id = uuid.uuid4()
    jd, skill, _ = _make_jd_with_skill(db_session, org_id, "TOSSK1")

    headers = auth_headers(org_id=org_id, permissions=[permissions.REQUIREMENTS_READ])
    response = client.patch(
        f"/api/v1/jd-analysis/{jd.id}/skills/{skill.id}", json={"name": "Advanced Python"}, headers=headers
    )
    assert response.status_code == 403


def test_patch_skill_updates_name_and_description(client, db_session):
    org_id = uuid.uuid4()
    jd, skill, _ = _make_jd_with_skill(db_session, org_id, "TOSSK2")

    headers = auth_headers(org_id=org_id, permissions=[permissions.REQUIREMENTS_WRITE], email="editor@example.com")
    response = client.patch(
        f"/api/v1/jd-analysis/{jd.id}/skills/{skill.id}",
        json={"name": "Advanced Python", "description": "Updated"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Advanced Python"
    assert body["description"] == "Updated"

    # Parent JD stamps modified_by/modified_at even though Skill itself has no such column.
    read_headers = auth_headers(org_id=org_id, permissions=[permissions.REQUIREMENTS_READ])
    jd_response = client.get(f"/api/v1/jd-analysis/{jd.id}", headers=read_headers)
    assert jd_response.json()["modified_by"] == "editor@example.com"
    assert jd_response.json()["modified_at"] is not None

    audit_response = client.get(f"/api/v1/jd-analysis/{jd.id}/audit-log", headers=read_headers)
    actions = [row["action"] for row in audit_response.json()]
    assert "skill_updated" in actions


def test_patch_skill_from_other_org_is_404(client, db_session):
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    jd, skill, _ = _make_jd_with_skill(db_session, org_b, "TOSSK3")

    headers = auth_headers(org_id=org_a, permissions=[permissions.REQUIREMENTS_WRITE])
    response = client.patch(f"/api/v1/jd-analysis/{jd.id}/skills/{skill.id}", json={"name": "x"}, headers=headers)
    assert response.status_code == 404


def test_patch_unknown_skill_id_is_404(client, db_session):
    org_id = uuid.uuid4()
    jd, _, _ = _make_jd_with_skill(db_session, org_id, "TOSSK4")

    headers = auth_headers(org_id=org_id, permissions=[permissions.REQUIREMENTS_WRITE])
    response = client.patch(
        f"/api/v1/jd-analysis/{jd.id}/skills/{uuid.uuid4()}", json={"name": "x"}, headers=headers
    )
    assert response.status_code == 404


def test_patch_rubric_requires_requirements_write(client, db_session):
    org_id = uuid.uuid4()
    jd, _, rubrics = _make_jd_with_skill(db_session, org_id, "TOSRB1")

    headers = auth_headers(org_id=org_id, permissions=[permissions.REQUIREMENTS_READ])
    response = client.patch(
        f"/api/v1/jd-analysis/{jd.id}/rubrics/{rubrics[0].id}", json={"description": "x"}, headers=headers
    )
    assert response.status_code == 403


def test_patch_rubric_updates_description(client, db_session):
    org_id = uuid.uuid4()
    jd, _, rubrics = _make_jd_with_skill(db_session, org_id, "TOSRB2")

    headers = auth_headers(org_id=org_id, permissions=[permissions.REQUIREMENTS_WRITE], email="editor@example.com")
    response = client.patch(
        f"/api/v1/jd-analysis/{jd.id}/rubrics/{rubrics[0].id}",
        json={"description": "Rewritten description"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Rewritten description"
    # weight untouched
    assert response.json()["weight_percentage"] == 60.0


def test_patch_rubric_weight_within_tolerance_of_100_succeeds(client, db_session):
    org_id = uuid.uuid4()
    jd, _, rubrics = _make_jd_with_skill(db_session, org_id, "TOSRB3", rubric_weights=(60, 40))

    headers = auth_headers(org_id=org_id, permissions=[permissions.REQUIREMENTS_WRITE])
    # 60.3 + 40 = 100.3, within +/-0.5 tolerance
    response = client.patch(
        f"/api/v1/jd-analysis/{jd.id}/rubrics/{rubrics[0].id}", json={"weight_percentage": 60.3}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["weight_percentage"] == 60.3


def test_patch_rubric_weight_breaking_100_sum_is_rejected(client, db_session):
    org_id = uuid.uuid4()
    jd, _, rubrics = _make_jd_with_skill(db_session, org_id, "TOSRB4", rubric_weights=(60, 40))

    headers = auth_headers(org_id=org_id, permissions=[permissions.REQUIREMENTS_WRITE])
    # 90 + 40 = 130, well outside tolerance
    response = client.patch(
        f"/api/v1/jd-analysis/{jd.id}/rubrics/{rubrics[0].id}", json={"weight_percentage": 90}, headers=headers
    )
    assert response.status_code == 422

    # Confirm nothing was actually persisted.
    read_headers = auth_headers(org_id=org_id, permissions=[permissions.REQUIREMENTS_READ])
    jd_response = client.get(f"/api/v1/jd-analysis/{jd.id}", headers=read_headers)
    persisted_weight = next(
        r["weight_percentage"] for r in jd_response.json()["skills"][0]["rubrics"] if r["id"] == str(rubrics[0].id)
    )
    assert persisted_weight == 60.0


def test_patch_rubric_from_other_org_is_404(client, db_session):
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    jd, _, rubrics = _make_jd_with_skill(db_session, org_b, "TOSRB5")

    headers = auth_headers(org_id=org_a, permissions=[permissions.REQUIREMENTS_WRITE])
    response = client.patch(
        f"/api/v1/jd-analysis/{jd.id}/rubrics/{rubrics[0].id}", json={"description": "x"}, headers=headers
    )
    assert response.status_code == 404
