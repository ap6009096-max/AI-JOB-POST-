from __future__ import annotations

from contextlib import contextmanager
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.security import Principal, get_current_user
from app.db.models import Job, User
from app.db.repositories.companies import CompanyRepository
from app.db.repositories.users import UserRepository
from app.db.session import get_db
from app.graphs.job_graph import ALL_PIPELINE_NODES
from app.main import app
from app.schemas.gemini import GeneratedJob, GeneratedJobExperience, JobReview, JobReviewNote
from app.services.job_document import document_from_fields, fields_from_payload

client = TestClient(app)

LONG_DESCRIPTION = (
    "We need a Python developer to build hiring APIs, own Django services, "
    "and work with SQL and AWS in a product team based in Patna."
)

COMPLETE_JOB = {
    "title": "Python Developer",
    "description": LONG_DESCRIPTION,
    "location": "Patna",
    "required_skills": ["Python", "Django"],
    "preferred_skills": ["REST APIs"],
    "experience": {"years": 2, "text": "2+ years"},
    "education": "B.Tech in Computer Science",
    "technologies": ["PostgreSQL", "Redis"],
    "responsibilities": ["Build APIs"],
    "salary_range": "8-12 LPA",
    "employment_type": "full_time",
    "seniority": "junior",
    "certifications": [],
    "openings": 1,
    "deadline": "",
}

JOB_JSON_KEYS = set(
    document_from_fields(fields_from_payload(COMPLETE_JOB)).keys()
)


@contextmanager
def acting_as(user: User, db_session):
    memberships = CompanyRepository(db_session).list_for_user(user.id)

    def override_user() -> Principal:
        return Principal(user=user, claims={}, memberships=memberships)

    def override_db():
        yield db_session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def _user(db_session, *, role: str, email: str | None = None) -> User:
    return UserRepository(db_session).create(
        email=email or f"{role}-{uuid4().hex[:8]}@example.com",
        full_name="Pat Recruiter",
        role=role,
    )


def _company_with_member(db_session, *, role: str, membership_role: str, name: str = "Acme"):
    user = _user(db_session, role=role)
    company = CompanyRepository(db_session).create(name=name)
    CompanyRepository(db_session).add_member(
        company_id=company.id, user_id=user.id, role=membership_role
    )
    db_session.flush()
    return user, company


def _install_job_pipeline_mocks(monkeypatch, *, configured: bool = True, review: JobReview | None = None) -> None:
    monkeypatch.setattr("app.graphs.job_nodes.is_configured", lambda: configured)
    monkeypatch.setattr(
        "app.graphs.job_nodes.review_job",
        lambda _job: review or JobReview(overall="Looks solid", notes=[]),
    )


def _step_names(body: dict) -> list[str]:
    pipeline = body.get("pipeline") or {}
    return [item["node"] for item in pipeline.get("steps") or []]


def _check_statuses(body: dict, field: str) -> set[str]:
    pipeline = body.get("pipeline") or {}
    return {item["status"] for item in pipeline.get("checks") or [] if item.get("field") == field}


def _generated_job() -> GeneratedJob:
    return GeneratedJob(
        title="Python Developer",
        description=LONG_DESCRIPTION,
        required_skills=["Python", "Django", "SQL", "AWS"],
        preferred_skills=["REST APIs"],
        experience=GeneratedJobExperience(years=2, text="0-2 years"),
        education="Bachelor's in Computer Science or equivalent",
        technologies=["Python", "Django", "SQL", "AWS"],
        responsibilities=["Build APIs", "Write tests"],
        location="Patna",
        salary_range="₹4–8 LPA",
        employment_type="full_time",
        seniority="junior",
        certifications=[],
        openings=1,
        deadline="",
    )


def test_ai_and_manual_jobs_share_job_json_keys() -> None:
    manual = document_from_fields(fields_from_payload(COMPLETE_JOB))
    generated = document_from_fields(fields_from_payload(_generated_job().model_dump()))
    assert set(manual) == set(generated) == JOB_JSON_KEYS


def test_job_pipeline_records_every_node_and_stays_draft(db_session, monkeypatch) -> None:
    _install_job_pipeline_mocks(monkeypatch)
    recruiter, _company = _company_with_member(db_session, role="recruiter", membership_role="recruiter")
    with acting_as(recruiter, db_session):
        created = client.post("/v1/jobs", json=COMPLETE_JOB)
        assert created.status_code == 201
        job_id = created.json()["id"]
        response = client.post(f"/v1/jobs/{job_id}/pipeline")
        fetched = client.get(f"/v1/jobs/{job_id}")
    assert response.status_code == 200
    body = response.json()
    assert _step_names(body) == ALL_PIPELINE_NODES
    assert body["status"] == "draft"
    assert set(body) - {"pipeline", "embedding_id", "has_job_json"} == JOB_JSON_KEYS
    assert body["pipeline"]["status"] in {"completed", "completed_with_errors"}
    assert "complete" in _check_statuses(body, "required_skills")
    assert fetched.json()["pipeline"]["checks"]
    row = db_session.get(Job, UUID(job_id))
    assert row is not None
    assert row.status == "draft"
    assert set(row.requirements["job_json"]) == JOB_JSON_KEYS
    assert row.requirements["job_pipeline"]["current_node"] == "create_job_json"


def test_missing_skills_are_reported(db_session, monkeypatch) -> None:
    _install_job_pipeline_mocks(monkeypatch)
    recruiter, _company = _company_with_member(db_session, role="recruiter", membership_role="recruiter")
    payload = {**COMPLETE_JOB, "required_skills": []}
    with acting_as(recruiter, db_session):
        created = client.post("/v1/jobs", json=payload)
        job_id = created.json()["id"]
        response = client.post(f"/v1/jobs/{job_id}/pipeline")
    assert response.status_code == 200
    body = response.json()
    assert "missing" in _check_statuses(body, "required_skills")
    assert body["pipeline"]["status"] == "validation_failed"
    assert body["status"] == "draft"


def test_duplicate_title_is_invalid(db_session, monkeypatch) -> None:
    _install_job_pipeline_mocks(monkeypatch)
    recruiter, _company = _company_with_member(db_session, role="recruiter", membership_role="recruiter")
    with acting_as(recruiter, db_session):
        first = client.post("/v1/jobs", json=COMPLETE_JOB)
        second = client.post("/v1/jobs", json={**COMPLETE_JOB, "location": "Bengaluru"})
        assert first.status_code == 201
        assert second.status_code == 201
        response = client.post(f"/v1/jobs/{second.json()['id']}/pipeline")
    assert response.status_code == 200
    assert "invalid" in _check_statuses(response.json(), "title")
    assert response.json()["status"] == "draft"


def test_gemini_unconfigured_skips_review_and_still_writes_job_json(db_session, monkeypatch) -> None:
    _install_job_pipeline_mocks(monkeypatch, configured=False)
    recruiter, _company = _company_with_member(db_session, role="recruiter", membership_role="recruiter")
    with acting_as(recruiter, db_session):
        created = client.post("/v1/jobs", json=COMPLETE_JOB)
        job_id = created.json()["id"]
        response = client.post(f"/v1/jobs/{job_id}/pipeline")
    assert response.status_code == 200
    body = response.json()
    skipped = {item["node"] for item in (body.get("pipeline") or {}).get("skipped") or []}
    assert "Gemini_review" in skipped
    assert _step_names(body) == ALL_PIPELINE_NODES
    assert set(body) - {"pipeline", "embedding_id", "has_job_json"} == JOB_JSON_KEYS
    assert body["status"] == "draft"


def test_gemini_review_notes_are_recorded(db_session, monkeypatch) -> None:
    review = JobReview(
        overall="Salary is unclear",
        notes=[JobReviewNote(field="salary_range", status="ambiguous", message="Range is broad")],
    )
    _install_job_pipeline_mocks(monkeypatch, review=review)
    recruiter, _company = _company_with_member(db_session, role="recruiter", membership_role="recruiter")
    with acting_as(recruiter, db_session):
        created = client.post("/v1/jobs", json=COMPLETE_JOB)
        response = client.post(f"/v1/jobs/{created.json()['id']}/pipeline")
    assert response.status_code == 200
    body = response.json()
    assert body["pipeline"]["review"] == "Salary is unclear"
    assert "ambiguous" in _check_statuses(body, "salary_range")


def test_candidate_forbidden_on_job_pipeline(db_session) -> None:
    candidate = _user(db_session, role="candidate")
    with acting_as(candidate, db_session):
        response = client.post("/v1/jobs/00000000-0000-0000-0000-000000000001/pipeline")
    assert response.status_code == 403
    assert "Candidates cannot access" in response.json()["detail"]


def test_company_cannot_run_another_company_job_pipeline(db_session, monkeypatch) -> None:
    _install_job_pipeline_mocks(monkeypatch)
    owner_a, _company_a = _company_with_member(
        db_session, role="company_admin", membership_role="owner", name="Alpha"
    )
    owner_b, _company_b = _company_with_member(
        db_session, role="company_admin", membership_role="owner", name="Beta"
    )
    with acting_as(owner_a, db_session):
        created = client.post("/v1/jobs", json=COMPLETE_JOB)
        job_id = created.json()["id"]
    with acting_as(owner_b, db_session):
        response = client.post(f"/v1/jobs/{job_id}/pipeline")
        fetched = client.get(f"/v1/jobs/{job_id}")
    assert response.status_code == 404
    assert fetched.status_code == 404
