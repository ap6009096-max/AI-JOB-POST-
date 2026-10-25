from contextlib import contextmanager
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import Principal, get_current_user
from app.db.models import CandidateMatchScore, Job, MatchResult, MatchingRun, User
from app.db.repositories import EmbeddingRepository
from app.db.repositories.companies import CompanyRepository
from app.db.repositories.users import UserRepository
from app.db.session import get_db
from app.main import app
from app.services.candidates import CandidateService
from app.services.embedding_service import OWNER_CANDIDATE, OWNER_JOB
from app.services.gemini_service import EMBEDDING_MODEL

client = TestClient(app)

PUBLISHABLE_JOB = {
    "title": "Python Developer",
    "description": "Build hiring APIs with Python and FastAPI for recruiters in Bengaluru.",
    "location": "Bengaluru",
    "required_skills": ["Python"],
    "employment_type": "full_time",
    "technologies": ["FastAPI"],
    "education": "Bachelor in Computer Science",
    "salary_range": "12 LPA - 18 LPA",
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


def _user(db_session, *, role: str, full_name: str = "Pat Recruiter", status: str = "active") -> User:
    return UserRepository(db_session).create(
        email=f"{role}-{uuid4().hex[:8]}@example.com",
        full_name=full_name,
        role=role,
        status=status,
    )


def _company_with_member(db_session, *, role: str = "recruiter", membership_role: str = "recruiter", name: str = "Acme"):
    user = _user(db_session, role=role)
    company = CompanyRepository(db_session).create(name=name)
    CompanyRepository(db_session).add_member(company_id=company.id, user_id=user.id, role=membership_role)
    db_session.flush()
    return user, company


def _registered_candidate(
    db_session,
    *,
    name: str = "Asha Menon",
    skill: str = "Python",
    open_to_work: bool | None = None,
    location: str = "Bengaluru",
    technology: str | None = "FastAPI",
):
    user = _user(db_session, role="candidate", full_name=name)
    service = CandidateService(db_session)
    candidate = service.ensure_for_user(user.id)
    candidate.profile.headline = "Software Engineer"
    candidate.profile.location = location
    candidate.profile.summary = "Built FastAPI hiring tools with Python."
    if skill:
        service.create_skill(candidate.id, skill=skill)
    if technology:
        service.create_technology(candidate, name=technology)
    if open_to_work is not None:
        service.update_preferences(candidate, {"open_to_work": open_to_work})
    db_session.flush()
    return candidate


def _publish_job(client: TestClient, extra: dict | None = None) -> dict:
    payload = {**PUBLISHABLE_JOB, **(extra or {})}
    created = client.post("/v1/jobs", json=payload)
    assert created.status_code == 201
    job_id = created.json()["id"]
    published = client.post(f"/v1/jobs/{job_id}/publish")
    assert published.status_code == 200
    return published.json()


def test_draft_job_portal_rank_returns_400(db_session) -> None:
    recruiter, _company = _company_with_member(db_session)
    with acting_as(recruiter, db_session):
        created = client.post("/v1/jobs", json={"title": "Draft Role"})
        job_id = created.json()["id"]
        ranked = client.post(f"/v1/jobs/{job_id}/rank/portal?limit=10")
    assert ranked.status_code == 400
    assert "Publish the job first" in ranked.json()["detail"]


def test_published_job_ranks_only_registered_candidates(db_session) -> None:
    recruiter, _company = _company_with_member(db_session)
    asha = _registered_candidate(db_session, name="Asha Menon")
    _registered_candidate(db_session, name="Rohit Iyer", skill="Python")
    with acting_as(recruiter, db_session):
        job = _publish_job(client)
        ranked = client.post(f"/v1/jobs/{job['id']}/rank/portal?limit=10")
        listed = client.get("/v1/candidates/portal")
    assert ranked.status_code == 200
    body = ranked.json()
    assert body["track"] == "portal"
    ids = [row["candidate_id"] for row in body["results"]]
    assert ids
    assert all(not item.startswith("pc-") and not item.startswith("ec-") for item in ids)
    assert str(asha.id) in ids
    listed_ids = [row["id"] for row in listed.json()]
    assert str(asha.id) in listed_ids
    assert "pc-01" not in listed_ids


def test_eligibility_drops_closed_to_work(db_session) -> None:
    recruiter, _company = _company_with_member(db_session)
    open_candidate = _registered_candidate(db_session, name="Open Candidate")
    closed = _registered_candidate(db_session, name="Closed Candidate", open_to_work=False)
    with acting_as(recruiter, db_session):
        job = _publish_job(client)
        ranked = client.post(f"/v1/jobs/{job['id']}/rank/portal?limit=10")
    ids = [row["candidate_id"] for row in ranked.json()["results"]]
    assert str(open_candidate.id) in ids
    assert str(closed.id) not in ids


def test_vector_shortlist_prefers_closer_embedding(db_session) -> None:
    recruiter, _company = _company_with_member(db_session)
    near = _registered_candidate(db_session, name="Near Match")
    far = _registered_candidate(db_session, name="Far Match")
    with acting_as(recruiter, db_session):
        job_out = _publish_job(client)
    job = db_session.get(Job, UUID(job_out["id"]))
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
        owner_id=near.profile.id,
        model=EMBEDDING_MODEL,
        embedding=[1.0, 0.0, 0.0],
        content_hash="near",
    )
    far_row = repo.create(
        owner_type=OWNER_CANDIDATE,
        owner_id=far.profile.id,
        model=EMBEDDING_MODEL,
        embedding=[0.0, 0.0, 1.0],
        content_hash="far",
    )
    near.profile.embedding_id = near_row.id
    far.profile.embedding_id = far_row.id
    db_session.flush()
    with acting_as(recruiter, db_session):
        ranked = client.post(f"/v1/jobs/{job.id}/rank/portal?limit=10")
    assert ranked.status_code == 200
    results = ranked.json()["results"]
    assert results[0]["candidate_id"] == str(near.id)
    assert results[0]["parts"]["semantic"] > results[1]["parts"]["semantic"]


def test_matching_run_score_and_result_rows(db_session) -> None:
    recruiter, _company = _company_with_member(db_session)
    _registered_candidate(db_session, name="Asha Menon")
    with acting_as(recruiter, db_session):
        job = _publish_job(client)
        ranked = client.post(f"/v1/jobs/{job['id']}/rank/portal?limit=10")
    assert ranked.status_code == 200
    run_id = UUID(ranked.json()["id"])
    run = db_session.get(MatchingRun, run_id)
    assert run is not None
    assert run.track == "portal"
    assert run.status == "completed"
    scores = list(db_session.scalars(select(CandidateMatchScore).where(CandidateMatchScore.run_id == run_id)))
    results = list(db_session.scalars(select(MatchResult).where(MatchResult.run_id == run_id)))
    assert scores
    assert results
    assert len(scores) == len(ranked.json()["results"])
    assert {row.rank for row in results} == {row["rank"] for row in ranked.json()["results"]}
    assert all(row.candidate_id is not None for row in scores)
    assert all(row.candidate_id is not None for row in results)
    assert run.params.get("calculation_version") == "match-score-v2"
    assert all(row.parts.get("version") == "match-score-v2" for row in scores)
    assert all("weights" in row.parts for row in scores)
    ranked_row = ranked.json()["results"][0]
    assert ranked_row["calculation_version"] == "match-score-v2"
    assert ranked_row["narrative"] is None
    assert set(ranked_row["parts"]) >= {
        "skills",
        "experience",
        "projects",
        "education",
        "semantic",
        "technology",
        "location",
        "salary",
    }


def test_candidate_forbidden_on_portal_rank(db_session) -> None:
    recruiter, _company = _company_with_member(db_session)
    with acting_as(recruiter, db_session):
        job = _publish_job(client)
    candidate = _user(db_session, role="candidate")
    with acting_as(candidate, db_session):
        ranked = client.post(f"/v1/jobs/{job['id']}/rank/portal?limit=10")
        listed = client.get("/v1/candidates/portal")
    assert ranked.status_code == 403
    assert listed.status_code == 403


def test_other_company_portal_rank_404(db_session) -> None:
    owner_a, _company_a = _company_with_member(
        db_session, role="company_admin", membership_role="owner", name="Alpha"
    )
    owner_b, _company_b = _company_with_member(
        db_session, role="company_admin", membership_role="owner", name="Beta"
    )
    with acting_as(owner_a, db_session):
        job = _publish_job(client)
    with acting_as(owner_b, db_session):
        ranked = client.post(f"/v1/jobs/{job['id']}/rank/portal?limit=10")
    assert ranked.status_code == 404


def test_portal_rank_limits(db_session) -> None:
    recruiter, _company = _company_with_member(db_session)
    _registered_candidate(db_session, name="Asha Menon")
    with acting_as(recruiter, db_session):
        job = _publish_job(client)
        ok_10 = client.post(f"/v1/jobs/{job['id']}/rank/portal?limit=10")
        ok_20 = client.post(f"/v1/jobs/{job['id']}/rank/portal?limit=20")
        ok_100 = client.post(f"/v1/jobs/{job['id']}/rank/portal?limit=100")
        invalid = client.post(f"/v1/jobs/{job['id']}/rank/portal?limit=15")
    assert ok_10.status_code == 200
    assert ok_20.status_code == 200
    assert ok_100.status_code == 200
    assert invalid.status_code == 422
    assert ok_10.json()["limit"] == 100
    assert ok_10.json()["results"][0]["source"] == "AI Job Post Portal"
    assert "Python" in ok_10.json()["results"][0]["matched_requirements"]
    run = db_session.get(MatchingRun, UUID(ok_10.json()["id"]))
    assert run is not None
    assert run.params.get("limit") == 100


def test_internet_rank_excludes_registered_candidates(db_session, monkeypatch: object) -> None:
    monkeypatch.setattr("app.services.internet_sourcing._collect_github", lambda _q: ([], "disabled_in_test"))
    monkeypatch.setattr("app.services.reddit_service.search_for_job", lambda _job: [])
    monkeypatch.setattr("app.services.reddit_agent.is_configured", lambda: False)
    monkeypatch.setattr("app.api.jobs.search_for_job", lambda _job: [])
    monkeypatch.setattr("app.services.internet_sourcing.store.list_external", lambda: [])
    recruiter, _company = _company_with_member(db_session)
    registered = _registered_candidate(db_session, name="Asha Menon")
    with acting_as(recruiter, db_session):
        job = _publish_job(client)
        ranked = client.post(f"/v1/jobs/{job['id']}/rank/internet?limit=10")
    assert ranked.status_code == 200
    body = ranked.json()
    assert body["track"] == "internet"
    ids = [row["candidate_id"] for row in body["results"]]
    assert str(registered.id) not in ids
    assert all("Ranking engine" in row["reasons"][0] for row in body["results"]) if body["results"] else True
    run = db_session.get(MatchingRun, UUID(body["id"]))
    assert run is not None
    assert run.track == "internet"
    scores = list(db_session.scalars(select(CandidateMatchScore).where(CandidateMatchScore.run_id == run.id)))
    assert scores == []


class _FakeExplanation:
    explanation = "Python overlap is strong."
    evidence = "Skills and projects mention FastAPI."
    strengths = ["Python"]
    weaknesses = ["Experience years"]
    recommendation = "Advance to interview"
    score = 0.99


def test_gemini_narrative_cannot_change_python_score(db_session, monkeypatch) -> None:
    captured: dict = {}

    def fake_explain(_job, _candidate, scores):
        captured["scores"] = dict(scores)
        return _FakeExplanation()

    monkeypatch.setattr("app.services.portal_ranking.is_configured", lambda: True)
    monkeypatch.setattr("app.services.portal_ranking.generate_match_explanation", fake_explain)
    recruiter, _company = _company_with_member(db_session)
    _registered_candidate(db_session, name="Asha Menon")
    with acting_as(recruiter, db_session):
        job = _publish_job(client)
        ranked = client.post(f"/v1/jobs/{job['id']}/rank/portal?limit=10")
    assert ranked.status_code == 200
    row = ranked.json()["results"][0]
    assert row["score"] == captured["scores"]["score"]
    assert row["score"] != 0.99
    assert row["narrative"]["recommendation"] == "Advance to interview"
    assert row["reasons"][0] == "Advance to interview"
    run_id = UUID(ranked.json()["id"])
    stored = db_session.scalars(select(CandidateMatchScore).where(CandidateMatchScore.run_id == run_id)).first()
    assert stored is not None
    assert float(stored.score) == row["score"]
    assert stored.parts["narrative"]["recommendation"] == "Advance to interview"


def test_rank_skips_gemini_when_unconfigured(db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.services.portal_ranking.is_configured", lambda: False)

    def fail_explain(*_args, **_kwargs):
        raise AssertionError("Gemini must not be called when unconfigured")

    monkeypatch.setattr("app.services.portal_ranking.generate_match_explanation", fail_explain)
    recruiter, _company = _company_with_member(db_session)
    _registered_candidate(db_session, name="Asha Menon")
    with acting_as(recruiter, db_session):
        job = _publish_job(client)
        ranked = client.post(f"/v1/jobs/{job['id']}/rank/portal?limit=10")
    assert ranked.status_code == 200
    row = ranked.json()["results"][0]
    assert row["score"] is not None
    assert row["narrative"] is None
    assert row["calculation_version"] == "match-score-v2"


def test_get_latest_portal_rank_does_not_rerun(db_session) -> None:
    recruiter, _company = _company_with_member(db_session)
    _registered_candidate(db_session, name="Asha Menon")
    with acting_as(recruiter, db_session):
        job = _publish_job(client)
        missing = client.get(f"/v1/jobs/{job['id']}/rank/portal/latest")
        created = client.post(f"/v1/jobs/{job['id']}/rank/portal?limit=10")
        latest = client.get(f"/v1/jobs/{job['id']}/rank/portal/latest")
        again = client.get(f"/v1/jobs/{job['id']}/rank/portal/latest")
    assert missing.status_code == 404
    assert created.status_code == 200
    assert latest.status_code == 200
    assert again.status_code == 200
    assert latest.json()["id"] == created.json()["id"]
    assert again.json()["id"] == created.json()["id"]
    runs = list(
        db_session.scalars(select(MatchingRun).where(MatchingRun.job_id == UUID(job["id"]), MatchingRun.track == "portal"))
    )
    assert len(runs) == 1
    row = latest.json()["results"][0]
    assert row["source"] == "AI Job Post Portal"
    assert "Python" in row["matched_requirements"]
    assert isinstance(row["missing_requirements"], list)


def test_candidate_forbidden_on_latest_portal_rank(db_session) -> None:
    recruiter, _company = _company_with_member(db_session)
    with acting_as(recruiter, db_session):
        job = _publish_job(client)
    candidate = _user(db_session, role="candidate")
    with acting_as(candidate, db_session):
        latest = client.get(f"/v1/jobs/{job['id']}/rank/portal/latest")
    assert latest.status_code == 403


def test_other_company_latest_portal_rank_404(db_session) -> None:
    owner_a, _company_a = _company_with_member(
        db_session, role="company_admin", membership_role="owner", name="Alpha"
    )
    owner_b, _company_b = _company_with_member(
        db_session, role="company_admin", membership_role="owner", name="Beta"
    )
    with acting_as(owner_a, db_session):
        job = _publish_job(client)
        client.post(f"/v1/jobs/{job['id']}/rank/portal?limit=10")
    with acting_as(owner_b, db_session):
        latest = client.get(f"/v1/jobs/{job['id']}/rank/portal/latest")
    assert latest.status_code == 404
