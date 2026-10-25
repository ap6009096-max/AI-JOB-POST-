from __future__ import annotations

from contextlib import contextmanager
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import Principal, get_current_user
from app.db.models import Embedding, Job, User
from app.db.repositories.companies import CompanyRepository
from app.db.repositories.users import UserRepository
from app.db.session import get_db
from app.main import app
from app.schemas.gemini import JobReview
from app.services.candidates import CandidateService
from app.services.embedding_service import (
    candidate_embedding_text,
    job_embedding_text,
    upsert_for_candidate,
    upsert_for_job,
)
from app.services.job_document import document_from_job

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
}


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


def _user(db_session, *, role: str) -> User:
    return UserRepository(db_session).create(
        email=f"{role}-{uuid4().hex[:8]}@example.com",
        full_name="Pat Recruiter",
        role=role,
    )


def _company_with_member(db_session, *, role: str = "recruiter", membership_role: str = "recruiter", name: str = "Acme"):
    user = _user(db_session, role=role)
    company = CompanyRepository(db_session).create(name=name)
    CompanyRepository(db_session).add_member(company_id=company.id, user_id=user.id, role=membership_role)
    db_session.flush()
    return user, company


def _mock_embed(monkeypatch) -> list[str]:
    calls: list[str] = []
    monkeypatch.setattr("app.services.embedding_service.is_configured", lambda: True)

    def fake_embed(text: str) -> list[float]:
        calls.append(text)
        return [0.03] * 768

    monkeypatch.setattr("app.services.embedding_service.embed_text", fake_embed)
    return calls


def test_candidate_embedding_text_uses_required_sections() -> None:
    text = candidate_embedding_text(
        {
            "summary": "Builds hiring tools",
            "skills": [{"skill": "Python"}],
            "experience": [{"title": "Engineer", "company_name": "Acme", "description": "APIs"}],
            "projects": [{"name": "Job Board", "description": "Matching"}],
            "technologies": [{"name": "FastAPI"}],
            "education": [{"school": "IIT", "degree": "B.Tech", "field_of_study": "CS"}],
        }
    )
    assert "Skills:" in text
    assert "Python" in text
    assert "Relevant Experience:" in text
    assert "Acme" in text
    assert "Projects:" in text
    assert "Job Board" in text
    assert "Technologies:" in text
    assert "FastAPI" in text
    assert "Education:" in text
    assert "IIT" in text
    assert "Professional Summary:" in text
    assert "Builds hiring tools" in text


def test_job_embedding_text_excludes_salary_and_location() -> None:
    text = job_embedding_text(
        {
            "title": "Python Developer",
            "description": LONG_DESCRIPTION,
            "location": "Bengaluru",
            "required_skills": ["Python"],
            "preferred_skills": ["Django"],
            "responsibilities": ["Build APIs"],
            "technologies": ["PostgreSQL"],
            "salary_range": "8-12 LPA",
        }
    )
    assert "Job Title:" in text
    assert "Description:" in text
    assert "Required Skills:" in text
    assert "Preferred Skills:" in text
    assert "Responsibilities:" in text
    assert "Technologies:" in text
    assert "Python" in text
    assert "Bengaluru" not in text
    assert "8-12" not in text
    assert "LPA" not in text


def test_embedding_text_strips_protected_disclosures() -> None:
    text = candidate_embedding_text(
        {
            "summary": "Builds hiring tools",
            "skills": [{"skill": "Python"}],
            "gender": "female",
            "race": "prefer_not_to_say",
            "demographics": {"age": 29},
        }
    )
    assert "Python" in text
    assert "female" not in text
    assert "prefer_not_to_say" not in text
    assert "29" not in text


def test_upsert_job_caches_unchanged_text_and_keeps_embedding_id(db_session, monkeypatch) -> None:
    calls = _mock_embed(monkeypatch)
    recruiter, company = _company_with_member(db_session)
    with acting_as(recruiter, db_session):
        created = client.post("/v1/jobs", json=COMPLETE_JOB)
    job = db_session.get(Job, UUID(created.json()["id"]))
    first = upsert_for_job(db_session, job)
    first_id = first.row.id
    second = upsert_for_job(db_session, job)
    db_session.flush()
    assert first.cached is False
    assert second.cached is True
    assert second.row.id == first_id
    assert job.embedding_id == first_id
    assert len(calls) == 1
    blob = job.requirements if isinstance(job.requirements, dict) else {}
    assert "embedding" not in blob
    assert job.embedding_id not in (None, "")
    stored = db_session.get(Embedding, first_id)
    assert stored is not None
    assert len(stored.embedding) == 768
    assert stored.content_hash


def test_upsert_candidate_does_not_store_vector_in_extras(db_session, monkeypatch) -> None:
    _mock_embed(monkeypatch)
    user = _user(db_session, role="candidate")
    candidate = CandidateService(db_session).ensure_for_user(user.id)
    master = {
        "summary": "Builds hiring tools",
        "skills": [{"skill": "Python"}],
        "experience": [{"title": "Engineer", "company_name": "Acme", "description": "APIs"}],
        "projects": [{"name": "Board", "description": "Hiring"}],
        "technologies": [{"name": "FastAPI"}],
        "education": [{"school": "IIT", "degree": "B.Tech", "field_of_study": "CS"}],
    }
    result = upsert_for_candidate(db_session, candidate.profile, master)
    db_session.flush()
    extras = dict(candidate.profile.extras or {})
    assert result.row is not None
    assert candidate.profile.embedding_id == result.row.id
    assert extras.get("embedding") is None
    assert "master_candidate" not in extras or extras.get("embedding") is None
    assert db_session.get(Embedding, result.row.id).owner_type == "candidate_profile"


def test_job_pipeline_sets_embedding_id_and_stays_draft(db_session, monkeypatch) -> None:
    _mock_embed(monkeypatch)
    monkeypatch.setattr("app.graphs.job_nodes.is_configured", lambda: True)
    monkeypatch.setattr(
        "app.graphs.job_nodes.review_job",
        lambda _job: JobReview(overall="Looks solid", notes=[]),
    )
    recruiter, _company = _company_with_member(db_session)
    with acting_as(recruiter, db_session):
        created = client.post("/v1/jobs", json=COMPLETE_JOB)
        job_id = created.json()["id"]
        response = client.post(f"/v1/jobs/{job_id}/pipeline")
        meta = client.get(f"/v1/jobs/{job_id}/embedding")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "draft"
    assert body["embedding_id"]
    assert meta.status_code == 200
    assert meta.json()["embedding_id"] == body["embedding_id"]
    row = db_session.get(Job, UUID(job_id))
    assert row.status == "draft"
    assert row.embedding_id is not None
    assert "embedding" not in (row.requirements or {})
    doc = document_from_job(row)
    assert "embedding" not in doc
    assert "embedding" not in (doc.get("requirements") or {})


def test_unconfigured_gemini_skips_embed_and_keeps_job_json(db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.services.embedding_service.is_configured", lambda: False)
    monkeypatch.setattr("app.graphs.job_nodes.is_configured", lambda: False)
    recruiter, _company = _company_with_member(db_session)
    with acting_as(recruiter, db_session):
        created = client.post("/v1/jobs", json=COMPLETE_JOB)
        job_id = created.json()["id"]
        response = client.post(f"/v1/jobs/{job_id}/pipeline")
        refresh = client.post(f"/v1/jobs/{job_id}/embedding")
    assert response.status_code == 200
    assert response.json()["title"] == "Python Developer"
    assert response.json().get("embedding_id") in {None, ""}
    assert db_session.get(Job, UUID(job_id)).status == "draft"
    assert refresh.status_code == 503


def test_candidate_forbidden_on_job_embedding_routes(db_session) -> None:
    candidate = _user(db_session, role="candidate")
    with acting_as(candidate, db_session):
        missing = client.get("/v1/jobs/00000000-0000-0000-0000-000000000001/embedding")
        refresh = client.post("/v1/jobs/00000000-0000-0000-0000-000000000001/embedding")
        similar = client.post("/v1/jobs/00000000-0000-0000-0000-000000000001/similar-candidates")
    assert missing.status_code == 403
    assert refresh.status_code == 403
    assert similar.status_code == 403


def test_company_cannot_read_another_company_job_embedding(db_session, monkeypatch) -> None:
    _mock_embed(monkeypatch)
    owner_a, _company_a = _company_with_member(db_session, role="company_admin", membership_role="owner", name="Alpha")
    owner_b, _company_b = _company_with_member(db_session, role="company_admin", membership_role="owner", name="Beta")
    with acting_as(owner_a, db_session):
        created = client.post("/v1/jobs", json=COMPLETE_JOB)
        job_id = created.json()["id"]
        client.post(f"/v1/jobs/{job_id}/embedding")
    with acting_as(owner_b, db_session):
        meta = client.get(f"/v1/jobs/{job_id}/embedding")
        refresh = client.post(f"/v1/jobs/{job_id}/embedding")
        similar = client.post(f"/v1/jobs/{job_id}/similar-candidates")
    assert meta.status_code == 404
    assert refresh.status_code == 404
    assert similar.status_code == 404


def test_refresh_job_embedding_is_cached_on_second_call(db_session, monkeypatch) -> None:
    calls = _mock_embed(monkeypatch)
    recruiter, _company = _company_with_member(db_session)
    with acting_as(recruiter, db_session):
        created = client.post("/v1/jobs", json=COMPLETE_JOB)
        job_id = created.json()["id"]
        first = client.post(f"/v1/jobs/{job_id}/embedding")
        second = client.post(f"/v1/jobs/{job_id}/embedding")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["embedding_id"] == second.json()["embedding_id"]
    assert second.json()["cached"] is True
    assert len(calls) == 1
    assert db_session.scalar(select(Embedding)) is not None
