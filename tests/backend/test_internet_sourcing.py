from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.core.security import Principal, get_current_user
from app.db.models import ExternalCandidate, Job, MatchingRun, MatchResult, SourcingRun, User
from app.db.repositories.companies import CompanyRepository
from app.db.repositories.users import UserRepository
from app.db.session import get_db
from app.main import app
from app.schemas.source import SourceAgentResult, utc_now
from app.services.candidates import CandidateService
from app.services.source_fetch import FetchResult

client = TestClient(app)


@pytest.fixture(autouse=True)
def unconfigured_live_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.github_agent.settings.github_token", None)
    monkeypatch.setattr("app.services.reddit_agent.settings.reddit_client_id", None)
    monkeypatch.setattr("app.services.reddit_agent.settings.reddit_client_secret", None)
    monkeypatch.setattr("app.graphs.job_nodes.is_configured", lambda: False)
    monkeypatch.setattr("app.services.embedding_service.is_configured", lambda: False)
    monkeypatch.setattr("app.services.internet_sourcing.is_configured", lambda: False)
    monkeypatch.setattr("app.services.portal_ranking.is_configured", lambda: False)

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


def _registered_candidate(db_session, *, name: str = "Asha Menon", skill: str = "Python"):
    user = _user(db_session, role="candidate", full_name=name)
    service = CandidateService(db_session)
    candidate = service.ensure_for_user(user.id)
    candidate.profile.headline = "Software Engineer"
    candidate.profile.summary = "Built FastAPI hiring tools with Python."
    if skill:
        service.create_skill(candidate.id, skill=skill)
    db_session.flush()
    return candidate


def _publish_job(http: TestClient, extra: dict | None = None) -> dict:
    payload = {**PUBLISHABLE_JOB, **(extra or {})}
    created = http.post("/v1/jobs", json=payload)
    assert created.status_code == 201
    job_id = created.json()["id"]
    published = http.post(f"/v1/jobs/{job_id}/publish")
    assert published.status_code == 200
    return published.json()


def test_published_internet_search_persists_top_100(db_session) -> None:
    recruiter, _company = _company_with_member(db_session)
    asha = _registered_candidate(db_session)
    with acting_as(recruiter, db_session):
        job = _publish_job(client)
        ranked = client.post(f"/v1/jobs/{job['id']}/rank/internet?limit=10")
    assert ranked.status_code == 200
    body = ranked.json()
    assert body["track"] == "internet"
    assert body["limit"] == 100
    assert body["results"]
    assert all("Ranking engine" in row["reasons"][0] for row in body["results"])
    row = body["results"][0]
    assert row["url"]
    assert row["confidence"] == row["score"]
    assert "projects" in row["parts"]
    assert isinstance(row["matched_requirements"], list)
    assert row["narrative"]["evidence"]
    ids = [row["candidate_id"] for row in body["results"]]
    assert str(asha.id) not in ids
    assert all(not item.startswith("reddit-") for item in ids)
    skipped = {item["source"]: item["reason"] for item in body["skipped"]}
    assert skipped["LinkedIn"] == "linkedin_requires_authorized_api"
    assert skipped["GitHub"] == "github_unconfigured"
    assert skipped["Reddit"] == "reddit_unconfigured"
    sourcing = list(db_session.scalars(select(SourcingRun).where(SourcingRun.job_id == UUID(job["id"]))))
    matching = list(
        db_session.scalars(
            select(MatchingRun).where(MatchingRun.job_id == UUID(job["id"]), MatchingRun.track == "internet")
        )
    )
    assert len(sourcing) == 1
    assert sourcing[0].status == "completed"
    assert sourcing[0].query.get("skipped")
    assert len(matching) == 1
    assert matching[0].params["limit"] == 100
    assert matching[0].params.get("calculation_version") == "match-score-v2"


def test_latest_internet_rank_does_not_rerun(db_session) -> None:
    recruiter, _company = _company_with_member(db_session)
    with acting_as(recruiter, db_session):
        job = _publish_job(client)
        missing = client.get(f"/v1/jobs/{job['id']}/rank/internet/latest")
        created = client.post(f"/v1/jobs/{job['id']}/rank/internet?limit=20")
        latest = client.get(f"/v1/jobs/{job['id']}/rank/internet/latest")
        again = client.get(f"/v1/jobs/{job['id']}/rank/internet/latest")
    assert missing.status_code == 404
    assert created.status_code == 200
    assert latest.status_code == 200
    assert again.status_code == 200
    assert latest.json()["id"] == created.json()["id"]
    assert again.json()["id"] == created.json()["id"]
    assert latest.json()["limit"] == 100
    latest_row = latest.json()["results"][0]
    assert "Ranking engine" in latest_row["reasons"][0]
    assert latest_row["url"]
    assert latest_row["confidence"] == latest_row["score"]
    assert "projects" in latest_row["parts"]
    assert isinstance(latest_row["matched_requirements"], list)
    sourcing = list(db_session.scalars(select(SourcingRun).where(SourcingRun.job_id == UUID(job["id"]))))
    matching = list(
        db_session.scalars(
            select(MatchingRun).where(MatchingRun.job_id == UUID(job["id"]), MatchingRun.track == "internet")
        )
    )
    assert len(sourcing) == 1
    assert len(matching) == 1


def test_portal_rank_never_returns_internet_ids(db_session) -> None:
    recruiter, _company = _company_with_member(db_session)
    asha = _registered_candidate(db_session)
    with acting_as(recruiter, db_session):
        job = _publish_job(client)
        portal = client.post(f"/v1/jobs/{job['id']}/rank/portal?limit=10")
        internet = client.post(f"/v1/jobs/{job['id']}/rank/internet?limit=10")
    portal_ids = [row["candidate_id"] for row in portal.json()["results"]]
    internet_ids = [row["candidate_id"] for row in internet.json()["results"]]
    assert portal_ids
    assert all(not item.startswith("ec-") and not item.startswith("reddit-") for item in portal_ids)
    assert str(asha.id) in portal_ids
    assert str(asha.id) not in internet_ids


def test_linkedin_agent_is_not_http_fetched(db_session, monkeypatch) -> None:

    def boom_fetch(url: str, **_kwargs):
        if "linkedin" in url.lower():
            raise AssertionError("LinkedIn HTTP must not run")
        return FetchResult(ok=False, url=url, fetch_status="failed", skip_reason="blocked_in_test")

    def boom_github(url: str, **_kwargs):
        if "linkedin" in url.lower():
            raise AssertionError("LinkedIn HTTP must not run")
        return FetchResult(ok=False, url=url, fetch_status="failed", skip_reason="blocked_in_test")

    monkeypatch.setattr("app.services.source_fetch.fetch_public", boom_fetch)
    monkeypatch.setattr("app.services.portfolio_agent.fetch_public", boom_fetch)
    monkeypatch.setattr("app.services.website_agent.fetch_public", boom_fetch)
    monkeypatch.setattr("app.services.github_agent.github_api_get", boom_github)
    recruiter, _company = _company_with_member(db_session)
    with acting_as(recruiter, db_session):
        job = _publish_job(client)
        ranked = client.post(f"/v1/jobs/{job['id']}/rank/internet?limit=10")
    assert ranked.status_code == 200
    skipped = {item["source"]: item["reason"] for item in ranked.json()["skipped"]}
    assert skipped["LinkedIn"] == "linkedin_requires_authorized_api"


def test_live_github_hit_persists_uuid_and_match_results(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.internet_sourcing.github_agent.search_users",
        lambda *_args, **_kwargs: (["octocat"], None),
    )

    def fake_analyze(url: str) -> SourceAgentResult:
        return SourceAgentResult(
            url=url,
            analyzed_at=utc_now(),
            provenance="github_api",
            fetch_status="ok",
            evidence={
                "login": "octocat",
                "profile": {"name": "Octo Cat", "bio": "Python FastAPI", "blog": ""},
                "languages": ["Python"],
            },
            analysis={"skills": ["Python"]},
        )

    monkeypatch.setattr("app.services.internet_sourcing.github_agent.analyze", fake_analyze)
    recruiter, _company = _company_with_member(db_session)
    with acting_as(recruiter, db_session):
        job = _publish_job(client)
        ranked = client.post(f"/v1/jobs/{job['id']}/rank/internet?limit=10")
        details = client.get(f"/v1/candidates/external/{ranked.json()['results'][0]['candidate_id']}")
    assert ranked.status_code == 200
    body = ranked.json()
    assert body["limit"] == 100
    candidate_id = body["results"][0]["candidate_id"]
    UUID(candidate_id)
    assert not candidate_id.startswith("ec-")
    assert body["results"][0]["source"] == "GitHub"
    assert body["results"][0]["url"] == "https://github.com/octocat"
    assert body["results"][0]["confidence"] == body["results"][0]["score"]
    assert "projects" in body["results"][0]["parts"]
    assert "Python" in body["results"][0]["matched_requirements"]
    assert "Ranking engine" in body["results"][0]["reasons"][0]
    assert details.status_code == 200
    assert details.json()["track"] == "internet"
    externals = list(db_session.scalars(select(ExternalCandidate)))
    assert any(str(row.id) == candidate_id for row in externals)
    results = list(db_session.scalars(select(MatchResult).where(MatchResult.external_candidate_id == UUID(candidate_id))))
    assert results


def test_candidate_forbidden_on_latest_internet_rank(db_session) -> None:
    recruiter, _company = _company_with_member(db_session)
    with acting_as(recruiter, db_session):
        job = _publish_job(client)
        client.post(f"/v1/jobs/{job['id']}/rank/internet?limit=10")
    candidate = _user(db_session, role="candidate")
    with acting_as(candidate, db_session):
        latest = client.get(f"/v1/jobs/{job['id']}/rank/internet/latest")
    assert latest.status_code == 403


def test_draft_job_with_job_json_can_rank_internet(db_session) -> None:
    recruiter, _company = _company_with_member(db_session)
    with acting_as(recruiter, db_session):
        created = client.post("/v1/jobs", json=PUBLISHABLE_JOB)
        assert created.status_code == 201
        job_id = created.json()["id"]
        job = db_session.get(Job, UUID(job_id))
        assert job is not None
        extras = dict(job.requirements or {})
        extras["job_json"] = {"title": job.title, "required_skills": ["Python"]}
        job.requirements = extras
        flag_modified(job, "requirements")
        db_session.flush()
        ranked = client.post(f"/v1/jobs/{job_id}/rank/internet?limit=10")
    assert ranked.status_code == 200
    assert ranked.json()["track"] == "internet"
    assert ranked.json()["results"]
    assert created.json()["status"] == "draft"


def test_draft_job_without_job_json_cannot_rank_internet(db_session) -> None:
    recruiter, _company = _company_with_member(db_session)
    with acting_as(recruiter, db_session):
        created = client.post("/v1/jobs", json=PUBLISHABLE_JOB)
        assert created.status_code == 201
        ranked = client.post(f"/v1/jobs/{created.json()['id']}/rank/internet?limit=10")
    assert created.json()["status"] == "draft"
    assert not created.json().get("has_job_json")
    assert ranked.status_code == 400
    assert ranked.json()["detail"] == "Run the job pipeline first"


def test_internet_rank_survives_gemini_quota(db_session, monkeypatch) -> None:
    calls = {"n": 0}

    def boom(*_args, **_kwargs):
        calls["n"] += 1
        error = Exception("RESOURCE_EXHAUSTED")
        error.code = 429
        raise error

    monkeypatch.setattr("app.services.internet_sourcing.is_configured", lambda: True)
    monkeypatch.setattr("app.services.internet_sourcing.generate_match_explanation", boom)
    recruiter, _company = _company_with_member(db_session)
    with acting_as(recruiter, db_session):
        created = client.post("/v1/jobs", json=PUBLISHABLE_JOB)
        assert created.status_code == 201
        job_id = created.json()["id"]
        job = db_session.get(Job, UUID(job_id))
        assert job is not None
        extras = dict(job.requirements or {})
        extras["job_json"] = {"title": job.title, "required_skills": ["Python"]}
        job.requirements = extras
        flag_modified(job, "requirements")
        db_session.flush()
        ranked = client.post(f"/v1/jobs/{job_id}/rank/internet?limit=10")
    assert ranked.status_code == 200
    body = ranked.json()
    assert body["results"]
    assert len(body["results"]) > 1
    assert calls["n"] == 1
    assert "Ranking engine" in body["results"][0]["reasons"][0]
    assert body["skipped"]


def test_other_company_latest_internet_rank_404(db_session) -> None:
    owner_a, _company_a = _company_with_member(
        db_session, role="company_admin", membership_role="owner", name="Alpha"
    )
    owner_b, _company_b = _company_with_member(
        db_session, role="company_admin", membership_role="owner", name="Beta"
    )
    with acting_as(owner_a, db_session):
        job = _publish_job(client)
        client.post(f"/v1/jobs/{job['id']}/rank/internet?limit=10")
    with acting_as(owner_b, db_session):
        latest = client.get(f"/v1/jobs/{job['id']}/rank/internet/latest")
    assert latest.status_code == 404


def test_score_internet_candidates_uses_semantic(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.internet_sourcing import score_internet_candidates

    monkeypatch.setattr(
        "app.services.internet_sourcing._profile_semantic",
        lambda _profile, _job_vector, cache=None: 0.85,
    )
    job = {
        "title": "Python Developer",
        "required_skills": ["Python"],
        "requirements": {"skills": ["Python"]},
    }
    candidates = [
        {
            "id": "ext-1",
            "profile": {
                "name": "Ada",
                "title": "Engineer",
                "skills": ["Python"],
                "technologies": ["FastAPI"],
                "resume_summary": "Builds APIs",
            },
        }
    ]
    results = score_internet_candidates(job, candidates, 5, job_vector=[0.1, 0.2, 0.3])
    assert results[0]["parts"]["semantic"] == 0.85
    assert results[0]["calculation_version"] == "match-score-v2"


def test_score_internet_candidates_zero_semantic_without_job_vector() -> None:
    from app.services.internet_sourcing import score_internet_candidates

    results = score_internet_candidates(
        {"required_skills": ["Python"]},
        [{"id": "ext-1", "profile": {"name": "Ada", "skills": ["Python"]}}],
        5,
    )
    assert results[0]["parts"]["semantic"] == 0.0
