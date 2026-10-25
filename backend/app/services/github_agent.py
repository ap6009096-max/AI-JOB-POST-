from __future__ import annotations

import base64
import json
import logging
from urllib.parse import quote, urlparse

from app.core.config import settings
from app.schemas.source import SourceAgentResult, utc_now
from app.services.gemini_service import analyze_source, is_configured
from app.services.source_fetch import github_api_get, is_github_host

logger = logging.getLogger(__name__)

REPO_LIMIT = 8
SEARCH_LIMIT = 8
GITHUB_SKIP_STATUSES = {401, 403, 429}


def analyze(url: str) -> SourceAgentResult:
    login = github_login(url)
    if not login:
        return SourceAgentResult(
            url=url,
            analyzed_at=utc_now(),
            provenance="github_api",
            fetch_status="skipped_invalid_url",
            skip_reason="github_user_required",
        )
    token = settings.github_token.get_secret_value() if settings.github_token else None
    user = github_api_get(f"https://api.github.com/users/{login}", token=token)
    if not user.ok:
        return SourceAgentResult(
            url=url,
            analyzed_at=utc_now(),
            provenance="github_api",
            fetch_status=user.fetch_status or "failed",
            skip_reason=user.skip_reason or "github_user_unavailable",
        )
    profile = _loads(user.body)
    repos_fetch = github_api_get(
        f"https://api.github.com/users/{login}/repos?per_page={REPO_LIMIT}&sort=updated",
        token=token,
    )
    repos = _loads_list(repos_fetch.body) if repos_fetch.ok else []
    languages: dict[str, int] = {}
    readmes: list[dict[str, str]] = []
    projects: list[dict[str, str]] = []
    for repo in repos[:REPO_LIMIT]:
        name = str(repo.get("name") or "")
        full_name = str(repo.get("full_name") or f"{login}/{name}")
        if not name:
            continue
        projects.append(
            {
                "name": name,
                "description": str(repo.get("description") or ""),
                "url": str(repo.get("html_url") or ""),
                "language": str(repo.get("language") or ""),
            }
        )
        langs = github_api_get(f"https://api.github.com/repos/{full_name}/languages", token=token)
        if langs.ok:
            for language, bytes_count in _loads(langs.body).items():
                if isinstance(bytes_count, int):
                    languages[language] = languages.get(language, 0) + bytes_count
        readme = github_api_get(f"https://api.github.com/repos/{full_name}/readme", token=token)
        if readme.ok:
            readmes.append({"repo": name, "excerpt": _readme_excerpt(readme.body)})

    evidence = {
        "login": login,
        "profile": {
            "name": profile.get("name") or "",
            "bio": profile.get("bio") or "",
            "company": profile.get("company") or "",
            "blog": profile.get("blog") or "",
        },
        "repositories": projects,
        "languages": sorted(languages, key=lambda name: languages[name], reverse=True),
        "readmes": readmes,
    }
    snippet = _snippet(evidence)
    analysis = _source_analysis("github", url, snippet)
    return SourceAgentResult(
        url=url,
        analyzed_at=utc_now(),
        provenance="github_api",
        fetch_status="ok",
        evidence=evidence,
        analysis=analysis,
    )


def search_users(query: str, *, limit: int = SEARCH_LIMIT) -> tuple[list[str], str | None]:
    token = settings.github_token.get_secret_value() if settings.github_token else None
    if not token:
        return [], "github_unconfigured"
    q = quote((query or "").strip() or "developer")
    per_page = max(1, min(limit, 10))
    fetched = github_api_get(f"https://api.github.com/search/users?q={q}&per_page={per_page}", token=token)
    if not fetched.ok or fetched.status_code in GITHUB_SKIP_STATUSES:
        return [], fetched.skip_reason or "github_search_unavailable"
    payload = _loads(fetched.body)
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    logins: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        login = str(item.get("login") or "").strip()
        if login:
            logins.append(login)
        if len(logins) >= limit:
            break
    return logins, None


def github_login(url: str) -> str | None:
    parsed = urlparse((url or "").strip())
    if not is_github_host(parsed.hostname):
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if not parts or parts[0] in {"settings", "login", "orgs", "marketplace", "topics", "notifications"}:
        return None
    return parts[0]


def _loads(raw: str) -> dict:
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _loads_list(raw: str) -> list[dict]:
    try:
        payload = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _readme_excerpt(raw: str) -> str:
    payload = _loads(raw)
    encoded = payload.get("content") or ""
    if payload.get("encoding") == "base64" and encoded:
        try:
            decoded = base64.b64decode(encoded).decode("utf-8", errors="replace")
        except (ValueError, TypeError):
            decoded = str(encoded)
    else:
        decoded = str(encoded or raw)
    return decoded[:3000]


def _snippet(evidence: dict) -> str:
    profile = evidence.get("profile") or {}
    lines = [
        f"GitHub login: {evidence.get('login')}",
        f"Name: {profile.get('name')}",
        f"Bio: {profile.get('bio')}",
        f"Languages: {', '.join(evidence.get('languages') or [])}",
        "Repositories:",
    ]
    for repo in evidence.get("repositories") or []:
        lines.append(f"- {repo.get('name')}: {repo.get('description')} ({repo.get('language')})")
    for readme in evidence.get("readmes") or []:
        lines.append(f"README {readme.get('repo')}: {readme.get('excerpt')}")
    return "\n".join(lines)


def _source_analysis(source: str, url: str, snippet: str) -> dict:
    if not is_configured() or not snippet.strip():
        return {}
    try:
        return analyze_source(source, url, snippet).model_dump()
    except Exception:
        logger.info("github_gemini_skipped")
        return {}
