from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import Principal, get_current_user
from app.db.models import User
from app.db.repositories import EmbeddingRepository
from app.db.repositories.companies import CompanyRepository
from app.db.repositories.users import UserRepository
from app.db.session import get_db
from app.main import app
from app.services.candidates import CandidateService
from app.services.embedding_service import OWNER_CANDIDATE, OWNER_JOB
from app.services.gemini_service import EMBEDDING_MODEL
from app.services.vector_search import similar, similar_candidates_for_job

client = TestClient(app)


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


def _company_with_member(db_session, name: str = "Search Co"):
    user = _user(db_session, role="recruiter")
    company = CompanyRepository(db_session).create(name=name)
    CompanyRepository(db_session).add_member(company_id=company.id, user_id=user.id, role="recruiter")
    db_session.flush()
    return user, company


def _profile(db_session, *, summary: str):
    user = _user(db_session, role="candidate")
    candidate = CandidateService(db_session).ensure_for_user(user.id)
    candidate.profile.summary = summary
    db_session.flush()
    return candidate.profile


def test_similar_ranks_closer_vector_first(db_session) -> None:
    near = _profile(db_session, summary="near")
    far = _profile(db_session, summary="far")
    repo = EmbeddingRepository(db_session)
    near_row = repo.create(
        owner_type=OWNER_CANDIDATE,
        owner_id=near.id,
        model=EMBEDDING_MODEL,
        embedding=[1.0, 0.0, 0.0],
        content_hash="near",
    )
    repo.create(
        owner_type=OWNER_CANDIDATE,
        owner_id=far.id,
        model=EMBEDDING_MODEL,
        embedding=[0.0, 1.0, 0.0],
        content_hash="far",
    )
    near.embedding_id = near_row.id
    db_session.flush()
    hits = similar(db_session, [1.0, 0.0, 0.0], OWNER_CANDIDATE, limit=2)
    assert [item["owner_id"] for item in hits] == [str(near.id), str(far.id)]
    assert hits[0]["score"] > hits[1]["score"]


def test_similar_candidates_for_job_uses_job_embedding(db_session) -> None:
    recruiter, company = _company_with_member(db_session)
    with acting_as(recruiter, db_session):
        created = client.post("/v1/jobs", json={"title": "Python Developer", "description": "APIs"})
    from app.db.models import Job
    from uuid import UUID

    job = db_session.get(Job, UUID(created.json()["id"]))
    near = _profile(db_session, summary="python")
    far = _profile(db_session, summary="design")
    repo = EmbeddingRepository(db_session)
    job_row = repo.create(
        owner_type=OWNER_JOB,
        owner_id=job.id,
        model=EMBEDDING_MODEL,
        embedding=[1.0, 0.1, 0.0],
        content_hash="job",
    )
    job.embedding_id = job_row.id
    near_row = repo.create(
        owner_type=OWNER_CANDIDATE,
        owner_id=near.id,
        model=EMBEDDING_MODEL,
        embedding=[1.0, 0.0, 0.0],
        content_hash="near",
    )
    far_row = repo.create(
        owner_type=OWNER_CANDIDATE,
        owner_id=far.id,
        model=EMBEDDING_MODEL,
        embedding=[0.0, 0.0, 1.0],
        content_hash="far",
    )
    near.embedding_id = near_row.id
    far.embedding_id = far_row.id
    db_session.flush()
    hits = similar_candidates_for_job(db_session, job, limit=2)
    assert hits[0]["candidate_id"] == str(near.candidate_id)
    assert hits[0]["score"] > hits[1]["score"]
    with acting_as(recruiter, db_session):
        response = client.post(f"/v1/jobs/{job.id}/similar-candidates", params={"limit": 2})
    assert response.status_code == 200
    body = response.json()
    assert body[0]["candidate_id"] == str(near.candidate_id)


def test_similar_candidates_requires_job_embedding(db_session) -> None:
    recruiter, _company = _company_with_member(db_session)
    with acting_as(recruiter, db_session):
        created = client.post("/v1/jobs", json={"title": "Python Developer"})
        response = client.post(f"/v1/jobs/{created.json()['id']}/similar-candidates")
    assert response.status_code == 400
