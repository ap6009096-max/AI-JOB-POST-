from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
SEARCH_URL = "https://oauth.reddit.com/search"
TIMEOUT_SECONDS = 10.0
SKIP_STATUSES = {401, 403, 429}


def is_configured() -> bool:
    return settings.reddit_client_id is not None and settings.reddit_client_secret is not None


def search_posts(query: str, *, limit: int = 25) -> list[dict[str, Any]]:
    if not is_configured():
        logger.info("reddit_skipped reason=missing_credentials")
        return []
    token = _access_token()
    if not token:
        return []
    return _search(token, query, limit=limit)


def _access_token() -> str | None:
    assert settings.reddit_client_id is not None
    assert settings.reddit_client_secret is not None
    try:
        response = httpx.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(
                settings.reddit_client_id.get_secret_value(),
                settings.reddit_client_secret.get_secret_value(),
            ),
            headers={"User-Agent": settings.reddit_user_agent or "AIJobPost/0.1"},
            timeout=TIMEOUT_SECONDS,
        )
    except httpx.HTTPError:
        logger.info("reddit_token_failed")
        return None
    if response.status_code in SKIP_STATUSES or response.status_code >= 400:
        logger.info("reddit_token_skipped status=%s", response.status_code)
        return None
    payload = response.json()
    token = payload.get("access_token") if isinstance(payload, dict) else None
    return str(token) if token else None


def _search(token: str, query: str, *, limit: int) -> list[dict[str, Any]]:
    try:
        response = httpx.get(
            SEARCH_URL,
            params={"q": query[:512], "limit": min(limit, 25), "sort": "relevance", "type": "link"},
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": settings.reddit_user_agent or "AIJobPost/0.1",
            },
            timeout=TIMEOUT_SECONDS,
        )
    except httpx.HTTPError:
        logger.info("reddit_search_failed")
        return []
    if response.status_code in SKIP_STATUSES or response.status_code >= 400:
        logger.info("reddit_search_skipped status=%s", response.status_code)
        return []
    payload = response.json()
    children = ((payload.get("data") or {}).get("children") or []) if isinstance(payload, dict) else []
    posts: list[dict[str, Any]] = []
    for child in children:
        if not isinstance(child, dict):
            continue
        data = child.get("data")
        if isinstance(data, dict):
            posts.append(data)
    return posts
