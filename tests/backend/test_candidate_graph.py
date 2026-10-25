from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import Principal, get_current_user
from app.db.models import Embedding, User
from app.db.repositories.users import UserRepository
from app.db.session import get_db
from app.graphs.candidate_graph import ALL_PIPELINE_NODES
from app.main import app
from app.schemas.source import SourceAgentResult
from app.services.resume_parse import ResumeParseError

client = TestClient(app)

HAPPY_NODES = [
    "load_candidate",
    "load_resume",
    "extract_document",
    "analyze_resume",
    "analyze_github",
    "analyze_linkedin",
    "analyze_portfolio",
    "analyze_other_sources",
    "merge_sources",
    "normalize_candidate",
    "deduplicate",
    "validate_candidate",
    "create_master_candidate_json",
    "generate_candidate_embedding",
    "save_profile",
]


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


def _parse_result(**overrides) -> dict:
    payload = {
        "given_name": "Pat",
        "middle_name": "",
        "family_name": "Kumar",
        "email": "parsed@example.com",
        "phone": "",
        "address": "",
        "city": "Bengaluru",
        "country": "India",
        "current_role": "Engineer",
        "summary": "Builds hiring tools",
        "experience": [{"title": "Engineer", "company_name": "Acme", "start_date": "", "end_date": "", "description": ""}],
        "education": [],
        "skills": [{"skill": "Python", "years": 4}, {"skill": "python", "years": 2}],
        "technologies": [{"name": "FastAPI", "years": None}],
        "projects": [],
        "certifications": [],
        "achievements": [],
    }
    payload.update(overrides)
    return payload


def _ok_source(url: str, source: str, skills: list[str] | None = None) -> SourceAgentResult:
    return SourceAgentResult(
        url=url,
        analyzed_at="2026-01-01T00:00:00+00:00",
        provenance="test",
        fetch_status="ok",
        evidence={"url": url},
        analysis={"skills": skills or ["Python"], "summary": "Public professional evidence"},
    )


def _install_pipeline_mocks(monkeypatch, *, analyze_url=None, extract=None, embed=True) -> None:
    monkeypatch.setattr("app.graphs.candidate_nodes.is_configured", lambda: True)
    monkeypatch.setattr(
        "app.graphs.candidate_nodes.analyze_resume_text",
        lambda _text: _parse_result(),
    )
    if extract is not None:
        monkeypatch.setattr("app.graphs.candidate_nodes.extract_text", extract)
    if embed:
        monkeypatch.setattr("app.graphs.candidate_nodes.embed_text", lambda _text: [0.01] * 768)
    if analyze_url is None:
        def analyze_url(source: str, url: str) -> SourceAgentResult:
            if (source or "").lower() == "linkedin" or "linkedin.com" in url:
                from app.services.linkedin_agent import analyze as linkedin_analyze

                return linkedin_analyze(url)
            if "fail.example" in url:
                return SourceAgentResult(
                    url=url,
                    analyzed_at="2026-01-01T00:00:00+00:00",
                    provenance="test",
                    fetch_status="failed",
                    skip_reason="fetch_failed",
                )
            return _ok_source(url, source)
    monkeypatch.setattr("app.graphs.candidate_nodes.analyze_url", analyze_url)


def _step_names(body: dict) -> list[str]:
    pipeline = body.get("pipeline") or {}
    return [item["node"] for item in pipeline.get("steps") or []]


def _skip_reasons(body: dict) -> set[str]:
    pipeline = body.get("pipeline") or {}
    return {item["reason"] for item in pipeline.get("skipped") or []}


def test_happy_path_records_every_node_and_master_json(db_session, monkeypatch) -> None:
    _install_pipeline_mocks(monkeypatch)
    user = _user(db_session, role="candidate")
    original_email = user.email
    with acting_as(user, db_session):
        client.put("/v1/me/candidate/resume", json={"text": "Pat Kumar Python FastAPI", "url": ""})
        client.put(
            "/v1/me/candidate/professional-links",
            json={"linkedin": "", "github": "https://github.com/pat", "portfolio": "", "website": "", "other": []},
        )
        created_skill = client.post("/v1/me/candidate/skills", json={"skill": "ExistingSkill"})
        assert created_skill.status_code == 200
        response = client.post("/v1/me/candidate/pipeline")
    assert response.status_code == 200
    body = response.json()
    assert _step_names(body) == HAPPY_NODES
    assert ALL_PIPELINE_NODES == HAPPY_NODES
    with acting_as(user, db_session):
        profile_extras = client.get("/v1/me/candidate").json()
    assert profile_extras["personal"]["email"] == original_email
    assert [row["skill"] for row in profile_extras["skills"]] == ["ExistingSkill"]
    assert profile_extras["experience"] == []
    pipeline = profile_extras["pipeline"]
    assert pipeline["status"] in {"completed", "completed_with_errors"}
    from app.services.candidates import CandidateService

    service = CandidateService(db_session)
    candidate = service.get_by_user_id(user.id)
    assert candidate is not None
    master = (candidate.profile.extras or {}).get("master_candidate")
    assert master["given_name"] == "Pat"
    assert master["summary"]
    skills = [item["skill"].lower() for item in master["skills"]]
    assert skills.count("python") == 1
    embedding = db_session.scalar(select(Embedding).where(Embedding.owner_type == "candidate_profile"))
    assert embedding is not None
    assert len(embedding.embedding) == 768
    assert candidate.profile.embedding_id == embedding.id
    assert user.email == original_email


def test_missing_resume_skips_extract_and_still_analyzes_sources(db_session, monkeypatch) -> None:
    _install_pipeline_mocks(monkeypatch)
    user = _user(db_session, role="candidate")
    with acting_as(user, db_session):
        client.put(
            "/v1/me/candidate/professional-links",
            json={"linkedin": "", "github": "https://github.com/pat", "portfolio": "", "website": "", "other": []},
        )
        response = client.post("/v1/me/candidate/pipeline")
    assert response.status_code == 200
    names = _step_names(response.json())
    assert "extract_document" not in names
    assert "analyze_resume" not in names
    assert "analyze_github" in names
    assert "missing_resume" in _skip_reasons(response.json())


def test_invalid_url_and_linkedin_skip_without_html_fetch(db_session, monkeypatch) -> None:
    _install_pipeline_mocks(monkeypatch)

    def boom(*_args, **_kwargs):
        raise AssertionError("LinkedIn HTML must not be fetched")

    monkeypatch.setattr("app.services.source_fetch.fetch_public", boom)
    user = _user(db_session, role="candidate")
    with acting_as(user, db_session):
        client.put("/v1/me/candidate/resume", json={"text": "Pat Python engineer", "url": ""})
        client.put(
            "/v1/me/candidate/professional-links",
            json={
                "linkedin": "https://www.linkedin.com/in/pat",
                "github": "not-a-url",
                "portfolio": "",
                "website": "",
                "other": [],
            },
        )
        response = client.post("/v1/me/candidate/pipeline")
    assert response.status_code == 200
    reasons = _skip_reasons(response.json())
    assert "invalid_url" in reasons
    skipped_nodes = {item["node"] for item in (response.json()["pipeline"] or {}).get("skipped") or []}
    assert "analyze_linkedin" in skipped_nodes or "source_failure" in reasons


def test_source_failure_continues_to_merge(db_session, monkeypatch) -> None:
    _install_pipeline_mocks(monkeypatch)
    user = _user(db_session, role="candidate")
    with acting_as(user, db_session):
        client.put("/v1/me/candidate/resume", json={"text": "Pat Python engineer", "url": ""})
        client.put(
            "/v1/me/candidate/professional-links",
            json={
                "linkedin": "",
                "github": "https://github.com/pat",
                "portfolio": "https://fail.example/site",
                "website": "",
                "other": [],
            },
        )
        response = client.post("/v1/me/candidate/pipeline")
    assert response.status_code == 200
    assert "source_failure" in _skip_reasons(response.json())
    assert "merge_sources" in _step_names(response.json())
    assert "save_profile" in _step_names(response.json())


def test_extraction_failure_skips_analyze_resume(db_session, monkeypatch) -> None:
    _install_pipeline_mocks(
        monkeypatch,
        extract=lambda *_args, **_kwargs: (_ for _ in ()).throw(ResumeParseError("fail", stage="ocr")),
    )
    monkeypatch.setattr("app.graphs.candidate_nodes.get_bytes", lambda _key: b"%PDF-1.4")
    user = _user(db_session, role="candidate")
    with acting_as(user, db_session):
        seeded = client.get("/v1/me/candidate")
        assert seeded.status_code == 200
        from app.services.candidates import CandidateService

        service = CandidateService(db_session)
        candidate = service.get_by_user_id(user.id)
        assert candidate is not None
        service.update_resume_processing(
            candidate,
            {"object_key": "resumes/test.pdf", "content_type": "application/pdf", "text": ""},
        )
        db_session.flush()
        response = client.post("/v1/me/candidate/pipeline")
    assert response.status_code == 200
    names = _step_names(response.json())
    assert "extract_document" in names
    assert "analyze_resume" not in names
    assert "extraction_failure" in _skip_reasons(response.json())


def test_validation_failure_skips_embedding(db_session, monkeypatch) -> None:
    _install_pipeline_mocks(monkeypatch)
    user = _user(db_session, role="candidate")
    with acting_as(user, db_session):
        response = client.post("/v1/me/candidate/pipeline")
    assert response.status_code == 200
    body = response.json()
    assert body["pipeline"]["status"] == "validation_failed"
    assert "create_master_candidate_json" not in _step_names(body)
    assert "generate_candidate_embedding" not in _step_names(body)
    assert db_session.scalar(select(Embedding)) is None
    from app.services.candidates import CandidateService

    candidate = CandidateService(db_session).get_by_user_id(user.id)
    assert candidate is not None
    assert "master_candidate" not in (candidate.profile.extras or {})
    assert candidate.profile.extras["candidate_pipeline"]["status"] == "validation_failed"


def test_ai_failure_continues_without_crash(db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.graphs.candidate_nodes.is_configured", lambda: False)
    user = _user(db_session, role="candidate")
    with acting_as(user, db_session):
        client.put("/v1/me/candidate/resume", json={"text": "Pat Kumar Python", "url": ""})
        response = client.post("/v1/me/candidate/pipeline")
    assert response.status_code == 200
    assert "save_profile" in _step_names(response.json())
    assert "ai_failure" in _skip_reasons(response.json())
