from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import Principal, get_current_user
from app.db.models import AuditLog, Embedding, User
from app.db.repositories.users import UserRepository
from app.db.session import get_db
from app.main import app
from app.schemas.source import SourceAgentResult
from app.services.profile_sync import diff_master, fingerprint_evidence, merge_master

client = TestClient(app)


@contextmanager
def acting_as(user: User, db_session):
    def override_user() -> Principal:
        return Principal(user=user, claims={}, memberships=[])

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
        full_name="Pat Candidate",
        role=role,
    )


def _github_result(*repo_names: str) -> SourceAgentResult:
    repos = [{"name": name, "description": f"{name} app", "url": f"https://github.com/pat/{name}"} for name in repo_names]
    return SourceAgentResult(
        url="https://github.com/pat",
        analyzed_at="2026-01-01T00:00:00+00:00",
        provenance="github_api",
        fetch_status="ok",
        evidence={"login": "pat", "languages": ["Python"], "repositories": repos},
        analysis={"skills": ["Python", "FastAPI"], "summary": "From GitHub", "title": "Engineer"},
    )


def _install_source_mocks(monkeypatch, result: SourceAgentResult, *, embed: bool = True) -> list:
    calls: list[str] = []
    monkeypatch.setattr("app.services.source_service.analyze_url", lambda _source, _url: result)
    monkeypatch.setattr("app.services.embedding_service.is_configured", lambda: True)

    def fake_embed(text: str) -> list[float]:
        calls.append(text)
        return [0.02] * 768

    if embed:
        monkeypatch.setattr("app.services.embedding_service.embed_text", fake_embed)
    return calls


def test_fingerprint_changes_when_repo_added() -> None:
    first = fingerprint_evidence(_github_result("job-board"))
    second = fingerprint_evidence(_github_result("job-board", "hiring-api"))
    assert first != second
    assert fingerprint_evidence(_github_result("job-board")) == first


def test_merge_does_not_replace_summary_or_duplicate_python() -> None:
    current = {
        "summary": "Keep this summary",
        "skills": [{"skill": "Python", "years": 4}],
        "projects": [{"name": "job-board", "description": "", "url": ""}],
    }
    incoming = {
        "summary": "From GitHub",
        "skills": [{"skill": "python"}, {"skill": "FastAPI"}],
        "projects": [{"name": "hiring-api", "description": "New", "url": "https://github.com/pat/hiring-api"}],
    }
    merged = merge_master(current, incoming)
    assert merged["summary"] == "Keep this summary"
    skills = [item["skill"].lower() for item in merged["skills"]]
    assert skills.count("python") == 1
    assert "fastapi" in skills
    names = [item["name"].lower() for item in merged["projects"]]
    assert "job-board" in names
    assert "hiring-api" in names
    change = diff_master(current, merged)
    assert change["material"] is True
    assert "hiring-api" in change["added"]["projects"]


def test_merge_master_accepts_legacy_string_skills() -> None:
    merged = merge_master(
        {"skills": ["Python"], "technologies": ["FastAPI"]},
        {"skills": [{"skill": "TypeScript"}], "technologies": ["Postgres"]},
    )
    skills = [item["skill"] for item in merged["skills"]]
    techs = [item["name"] for item in merged["technologies"]]
    assert "Python" in skills
    assert "TypeScript" in skills
    assert "FastAPI" in techs
    assert "Postgres" in techs


def test_new_github_repo_versions_master_without_touching_standing(db_session, monkeypatch) -> None:
    result = _github_result("job-board")
    embed_calls = _install_source_mocks(monkeypatch, result)
    user = _user(db_session, role="candidate")
    original_email = user.email
    with acting_as(user, db_session):
        client.post("/v1/me/candidate/skills", json={"skill": "ExistingSkill"})
        client.put(
            "/v1/me/candidate/professional-links",
            json={"linkedin": "", "github": "https://github.com/pat", "portfolio": "", "website": "", "other": []},
        )
        response = client.post("/v1/me/candidate/sources/analyze")
    assert response.status_code == 200
    body = response.json()
    assert [row["skill"] for row in body["skills"]] == ["ExistingSkill"]
    assert body["email"] == original_email
    assert body["master_candidate"]["summary"] == "From GitHub"
    skills = [item["skill"].lower() for item in body["master_candidate"]["skills"]]
    assert "python" in skills
    assert len(body["profile_versions"]) == 1
    assert body["profile_versions"][0]["version"] == 1
    assert body["profile_versions"][0]["source"] == "github"
    logs = list(db_session.scalars(select(AuditLog).where(AuditLog.action == "candidate_profile_source_updated")))
    assert len(logs) == 1
    embedding = db_session.scalar(select(Embedding).where(Embedding.owner_type == "candidate_profile"))
    assert embedding is not None
    assert len(embedding.embedding) == 768
    assert embed_calls
    from app.services.candidates import CandidateService

    candidate = CandidateService(db_session).get_by_user_id(user.id)
    assert candidate is not None
    assert candidate.profile.embedding_id == embedding.id
    with acting_as(user, db_session):
        snapshot = client.get("/v1/me/candidate/profile-versions/1")
    assert snapshot.status_code == 200
    assert snapshot.json()["snapshot"]["summary"] == "From GitHub"


def test_unchanged_fetch_does_not_version_or_embed_again(db_session, monkeypatch) -> None:
    result = _github_result("job-board")
    embed_calls = _install_source_mocks(monkeypatch, result)
    user = _user(db_session, role="candidate")
    with acting_as(user, db_session):
        client.put(
            "/v1/me/candidate/professional-links",
            json={"linkedin": "", "github": "https://github.com/pat", "portfolio": "", "website": "", "other": []},
        )
        first = client.post("/v1/me/candidate/sources/analyze")
        second = client.post("/v1/me/candidate/sources/analyze")
    assert first.status_code == 200
    assert second.status_code == 200
    assert len(first.json()["profile_versions"]) == 1
    assert len(second.json()["profile_versions"]) == 1
    assert len(embed_calls) == 1


def test_new_repo_adds_project_and_increments_version(db_session, monkeypatch) -> None:
    embed_calls = _install_source_mocks(monkeypatch, _github_result("job-board"))
    user = _user(db_session, role="candidate")
    with acting_as(user, db_session):
        client.put(
            "/v1/me/candidate/professional-links",
            json={"linkedin": "", "github": "https://github.com/pat", "portfolio": "", "website": "", "other": []},
        )
        first = client.post("/v1/me/candidate/sources/analyze")
        monkeypatch.setattr(
            "app.services.source_service.analyze_url",
            lambda _source, _url: _github_result("job-board", "hiring-api"),
        )
        second = client.post("/v1/me/candidate/sources/analyze")
    assert first.status_code == 200
    assert second.status_code == 200
    assert len(second.json()["profile_versions"]) == 2
    names = [item["name"] for item in second.json()["master_candidate"]["projects"]]
    assert "job-board" in names
    assert "hiring-api" in names
    assert len(embed_calls) == 2


def test_pipeline_merges_instead_of_clobbering_summary(db_session, monkeypatch) -> None:
    from app.services.candidates import CandidateService
    from test_candidate_graph import _install_pipeline_mocks

    _install_pipeline_mocks(monkeypatch)
    user = _user(db_session, role="candidate")
    with acting_as(user, db_session):
        client.get("/v1/me/candidate")
        service = CandidateService(db_session)
        candidate = service.get_by_user_id(user.id)
        assert candidate is not None
        extras = dict(candidate.profile.extras or {})
        extras["master_candidate"] = {
            "summary": "Keep this summary",
            "given_name": "Pat",
            "skills": [{"skill": "Python"}],
        }
        candidate.profile.extras = extras
        db_session.flush()
        client.put("/v1/me/candidate/resume", json={"text": "Pat Kumar Python FastAPI", "url": ""})
        client.put(
            "/v1/me/candidate/professional-links",
            json={"linkedin": "", "github": "https://github.com/pat", "portfolio": "", "website": "", "other": []},
        )
        response = client.post("/v1/me/candidate/pipeline")
    assert response.status_code == 200
    master = response.json()["master_candidate"]
    assert master["summary"] == "Keep this summary"
    assert master["given_name"] == "Pat"
    assert len(response.json()["profile_versions"]) >= 1


def test_linkedin_skip_does_not_version(db_session, monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("LinkedIn HTML must not be fetched")

    monkeypatch.setattr("app.services.source_fetch.fetch_public", boom)
    user = _user(db_session, role="candidate")
    with acting_as(user, db_session):
        client.put(
            "/v1/me/candidate/professional-links",
            json={
                "linkedin": "https://www.linkedin.com/in/pat",
                "github": "",
                "portfolio": "",
                "website": "",
                "other": [],
            },
        )
        response = client.post("/v1/me/candidate/sources/analyze")
    assert response.status_code == 200
    assert response.json()["profile_versions"] == []
    assert response.json()["master_candidate"] is None
    linkedin = next(row for row in response.json()["links"] if row["source"] == "linkedin")
    assert linkedin["analysis"]["fetch_status"] == "skipped_linkedin_policy"
