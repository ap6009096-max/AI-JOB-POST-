from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.security import require_company_member
from app.data.seed import DEMO_JOB, DEMO_JOB_ID
from app.data.store import store
from app.db.session import get_db
from app.main import app
from app.services import reddit_agent, reddit_service

client = TestClient(app)

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
SEARCH_URL = "https://oauth.reddit.com/search"


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


@pytest.fixture(autouse=True)
def restore_externals() -> None:
    original = dict(store.external_candidates)
    yield
    store.external_candidates.clear()
    store.external_candidates.update(original)


@pytest.fixture
def reddit_creds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reddit_agent.settings, "reddit_client_id", SecretStr("test-client-id"))
    monkeypatch.setattr(reddit_agent.settings, "reddit_client_secret", SecretStr("test-client-secret"))
    monkeypatch.setattr(reddit_agent.settings, "reddit_user_agent", "AIJobPost/0.1")
    monkeypatch.setattr(reddit_service, "gemini_configured", lambda: False)


def _search_payload() -> dict[str, Any]:
    return {
        "data": {
            "children": [
                {
                    "data": {
                        "author": "pydev",
                        "title": "Built a FastAPI hiring board in Python",
                        "selftext": "Stack is Python, FastAPI, and React. Repo: https://github.com/pydev/hiring-board",
                        "permalink": "/r/Python/comments/abc/hiring_board/",
                        "subreddit": "Python",
                        "url": "https://github.com/pydev/hiring-board",
                    }
                },
                {
                    "data": {
                        "author": "pydev",
                        "title": "PostgreSQL ranking notes",
                        "selftext": "Used PostgreSQL for candidate search.",
                        "permalink": "/r/cscareerquestions/comments/def/ranking/",
                        "subreddit": "cscareerquestions",
                        "url": "https://www.reddit.com/r/cscareerquestions/comments/def/ranking/",
                    }
                },
                {
                    "data": {
                        "author": "[deleted]",
                        "title": "ignore me",
                        "selftext": "Python",
                        "permalink": "/r/Python/comments/gone/",
                        "subreddit": "Python",
                        "url": "https://www.reddit.com/r/Python/comments/gone/",
                    }
                },
            ]
        }
    }


def _install_http(monkeypatch: pytest.MonkeyPatch, *, token_status: int = 200, search_status: int = 200) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []

    def fake_post(url: str, **_kwargs: Any) -> FakeResponse:
        calls.append(("POST", url))
        payload = {"access_token": "reddit-token"} if token_status == 200 else {}
        return FakeResponse(token_status, payload)

    def fake_get(url: str, **_kwargs: Any) -> FakeResponse:
        calls.append(("GET", url))
        payload = _search_payload() if search_status == 200 else {}
        return FakeResponse(search_status, payload)

    monkeypatch.setattr(reddit_agent.httpx, "post", fake_post)
    monkeypatch.setattr(reddit_agent.httpx, "get", fake_get)
    return calls


def test_search_for_job_builds_unverified_evidence(monkeypatch: pytest.MonkeyPatch, reddit_creds: None) -> None:
    calls = _install_http(monkeypatch)
    hits = reddit_service.search_for_job(DEMO_JOB)
    assert [url for _method, url in calls] == [TOKEN_URL, SEARCH_URL]
    assert len(hits) == 1
    hit = hits[0]
    profile = hit["profile"]
    evidence = profile["reddit_evidence"]
    assert hit["id"] == "reddit-pydev"
    assert profile["name"] == "u/pydev"
    assert profile["source"] == "Reddit"
    assert profile["identity_status"] == "unverified_reddit_handle"
    assert evidence["source"] == "Reddit"
    assert evidence["source_url"] == "https://www.reddit.com/r/Python/comments/abc/hiring_board/"
    assert evidence["profile_identifier"] == "u/pydev"
    assert evidence["professional_evidence"]
    assert "Python" in evidence["skills"]
    assert "FastAPI" in evidence["skills"]
    assert "https://github.com/pydev/hiring-board" in evidence["projects"]
    assert evidence["relevant_experience"]
    assert evidence["timestamp"]
    assert "users" not in hit
    assert "professional_links" not in profile


def test_skills_in_text_matches_aliases() -> None:
    text = "Built dashboards in TS and Postgres"
    matched = reddit_service._skills_in_text(["TypeScript", "PostgreSQL", "Rust"], text)
    assert matched == ["TypeScript", "PostgreSQL"]


def test_missing_credentials_skips_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reddit_agent.settings, "reddit_client_id", None)
    monkeypatch.setattr(reddit_agent.settings, "reddit_client_secret", None)

    def boom(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("Reddit HTTP must not run without credentials")

    monkeypatch.setattr(reddit_agent.httpx, "post", boom)
    monkeypatch.setattr(reddit_agent.httpx, "get", boom)
    assert reddit_service.search_for_job(DEMO_JOB) == []


def test_unauthorized_token_skips_search(monkeypatch: pytest.MonkeyPatch, reddit_creds: None) -> None:
    calls = _install_http(monkeypatch, token_status=401)
    assert reddit_service.search_for_job(DEMO_JOB) == []
    assert calls == [("POST", TOKEN_URL)]


def test_internet_rank_stays_20_without_reddit_creds(monkeypatch: pytest.MonkeyPatch, db_session) -> None:
    monkeypatch.setattr(reddit_agent.settings, "reddit_client_id", None)
    monkeypatch.setattr(reddit_agent.settings, "reddit_client_secret", None)

    def boom(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("Reddit HTTP must not run without credentials")

    def override_db():
        yield db_session

    monkeypatch.setattr(reddit_agent.httpx, "post", boom)
    monkeypatch.setattr(reddit_agent.httpx, "get", boom)
    app.dependency_overrides[require_company_member] = lambda: object()
    app.dependency_overrides[get_db] = override_db
    try:
        response = client.post(f"/v1/jobs/{DEMO_JOB_ID}/rank/internet?limit=20")
    finally:
        app.dependency_overrides.pop(require_company_member, None)
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 20
    assert all(not row["candidate_id"].startswith("reddit-") for row in body["results"])


def test_rank_merges_reddit_hit_for_external_details(monkeypatch: pytest.MonkeyPatch, reddit_creds: None, db_session) -> None:
    _install_http(monkeypatch)

    def override_db():
        yield db_session

    app.dependency_overrides[require_company_member] = lambda: object()
    app.dependency_overrides[get_db] = override_db
    try:
        ranked = client.post(f"/v1/jobs/{DEMO_JOB_ID}/rank/internet?limit=20")
        details = client.get("/v1/candidates/external/reddit-pydev")
    finally:
        app.dependency_overrides.pop(require_company_member, None)
        app.dependency_overrides.pop(get_db, None)
    assert ranked.status_code == 200
    ranked_rows = ranked.json()["results"]
    assert len(ranked_rows) == 21
    assert "reddit-pydev" in [row["candidate_id"] for row in ranked_rows]
    assert details.status_code == 200
    profile = details.json()["profile"]
    assert profile["identity_status"] == "unverified_reddit_handle"
    assert profile["reddit_evidence"]["profile_identifier"] == "u/pydev"
    assert store.get_portal("reddit-pydev") is None
