from __future__ import annotations

import base64
import json
from contextlib import contextmanager
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import Principal, get_current_user
from app.db.models import User
from app.db.repositories.users import UserRepository
from app.db.session import get_db
from app.main import app
from app.services.source_fetch import FetchResult, fetch_public
from app.services import github_agent, linkedin_agent, source_fetch

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


class FakeResponse:
    def __init__(self, status_code: int, text: str, *, url: str, content_type: str = "text/html") -> None:
        self.status_code = status_code
        self.text = text
        self.content = text.encode()
        self.headers = {"content-type": content_type}
        self.url = url


class FakeClient:
    def __init__(self, routes: dict[str, FakeResponse]) -> None:
        self.routes = routes
        self.requested: list[str] = []

    def get(self, url: str, headers: dict | None = None) -> FakeResponse:
        self.requested.append(url)
        if url not in self.routes:
            raise AssertionError(f"unexpected fetch {url}")
        return self.routes[url]

    def close(self) -> None:
        return None


def _github_api(url: str, token: str | None = None, client=None) -> FetchResult:
    if url.endswith("/users/pat"):
        return FetchResult(ok=True, body='{"name":"Pat Kumar","bio":"Builds hiring tools"}', fetch_status="ok")
    if "/repos?" in url:
        return FetchResult(
            ok=True,
            fetch_status="ok",
            body=json.dumps(
                [
                    {
                        "name": "job-board",
                        "full_name": "pat/job-board",
                        "description": "Hiring app",
                        "html_url": "https://github.com/pat/job-board",
                        "language": "Python",
                    }
                ]
            ),
        )
    if url.endswith("/languages"):
        return FetchResult(ok=True, body='{"Python": 4000, "TypeScript": 1000}', fetch_status="ok")
    if url.endswith("/readme"):
        encoded = base64.b64encode(b"# Job Board\nFastAPI service").decode()
        return FetchResult(
            ok=True,
            fetch_status="ok",
            body=json.dumps({"encoding": "base64", "content": encoded}),
        )
    return FetchResult(ok=False, fetch_status="failed", skip_reason=url)


def test_github_analysis_stores_languages_and_provenance(db_session, monkeypatch) -> None:
    monkeypatch.setattr(github_agent, "github_api_get", _github_api)
    monkeypatch.setattr(github_agent, "is_configured", lambda: False)
    candidate = _user(db_session, role="candidate")
    with acting_as(candidate, db_session):
        saved = client.put(
            "/v1/me/candidate/professional-links",
            json={
                "linkedin": "",
                "github": "https://github.com/pat",
                "portfolio": "",
                "website": "",
                "other": [],
            },
        )
        assert saved.status_code == 200
        analyzed = client.post("/v1/me/candidate/sources/analyze")
    assert analyzed.status_code == 200
    github = next(row for row in analyzed.json()["links"] if row["source"] == "github")
    analysis = github["analysis"]
    assert analysis["provenance"] == "github_api"
    assert analysis["fetch_status"] == "ok"
    assert analysis["url"] == "https://github.com/pat"
    assert analysis["analyzed_at"]
    assert "Python" in analysis["evidence"]["languages"]
    assert analysis["evidence"]["repositories"][0]["name"] == "job-board"


def test_linkedin_does_not_fetch_http(monkeypatch) -> None:
    monkeypatch.setattr(
        source_fetch,
        "fetch_public",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("linkedin must not fetch")),
    )
    monkeypatch.setattr(
        source_fetch,
        "github_api_get",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("linkedin must not fetch")),
    )
    result = linkedin_agent.analyze("https://www.linkedin.com/in/pat")
    assert result.provenance == "candidate_provided"
    assert result.fetch_status == "skipped_linkedin_policy"
    assert result.skip_reason == "linkedin_requires_authorized_api"
    assert result.evidence["url"] == "https://www.linkedin.com/in/pat"


def test_linkedin_analyze_endpoint_skips_without_http(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        source_fetch,
        "fetch_public",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("linkedin must not fetch")),
    )
    candidate = _user(db_session, role="candidate")
    with acting_as(candidate, db_session):
        client.put(
            "/v1/me/candidate/professional-links",
            json={
                "linkedin": "https://linkedin.com/in/pat",
                "github": "",
                "portfolio": "",
                "website": "",
                "other": [],
            },
        )
        analyzed = client.post("/v1/me/candidate/sources/analyze")
    assert analyzed.status_code == 200
    linkedin = next(row for row in analyzed.json()["links"] if row["source"] == "linkedin")
    assert linkedin["analysis"]["fetch_status"] == "skipped_linkedin_policy"
    assert linkedin["analysis"]["provenance"] == "candidate_provided"


def test_robots_disallow_skips_page_fetch(monkeypatch) -> None:
    monkeypatch.setattr(source_fetch, "_assert_public_host", lambda _host: None)
    fake = FakeClient(
        {
            "https://portfolio.example/robots.txt": FakeResponse(
                200,
                "User-agent: *\nDisallow: /\n",
                url="https://portfolio.example/robots.txt",
                content_type="text/plain",
            )
        }
    )
    result = fetch_public("https://portfolio.example/work", client=fake)
    assert result.fetch_status == "skipped_robots"
    assert fake.requested == ["https://portfolio.example/robots.txt"]


def test_http_403_is_skipped_private(monkeypatch) -> None:
    monkeypatch.setattr(source_fetch, "_assert_public_host", lambda _host: None)
    fake = FakeClient(
        {
            "https://portfolio.example/robots.txt": FakeResponse(
                404,
                "missing",
                url="https://portfolio.example/robots.txt",
                content_type="text/plain",
            ),
            "https://portfolio.example/secret": FakeResponse(
                403,
                "forbidden",
                url="https://portfolio.example/secret",
            ),
        }
    )
    result = fetch_public("https://portfolio.example/secret", client=fake)
    assert result.fetch_status == "skipped_private"
    assert "403" in result.skip_reason


def test_private_ip_is_skipped_ssrf() -> None:
    result = fetch_public("http://127.0.0.1/")
    assert result.fetch_status == "skipped_ssrf"
    assert result.skip_reason == "private_or_reserved_ip"


def test_analyze_without_links_is_400(db_session) -> None:
    candidate = _user(db_session, role="candidate")
    with acting_as(candidate, db_session):
        response = client.post("/v1/me/candidate/sources/analyze")
    assert response.status_code == 400


def test_recruiter_cannot_analyze_sources(db_session) -> None:
    recruiter = _user(db_session, role="recruiter")
    with acting_as(recruiter, db_session):
        response = client.post("/v1/me/candidate/sources/analyze")
    assert response.status_code == 403
