from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any
from urllib.parse import urlparse

from app.data.skill_aliases import canonical_skill
from app.schemas.source import RedditEvidence, utc_now
from app.services.gemini_service import analyze_source, is_configured as gemini_configured
from app.services.reddit_agent import search_posts

logger = logging.getLogger(__name__)

SKIP_AUTHORS = {"", "[deleted]", "automoderator"}
REDDIT_HOSTS = {"reddit.com", "www.reddit.com", "old.reddit.com", "np.reddit.com", "oauth.reddit.com"}
URL_RE = re.compile(r"https?://[^\s)>\]]+", re.IGNORECASE)


def search_for_job(job: dict[str, Any]) -> list[dict[str, Any]]:
    query = _job_query(job)
    posts = search_posts(query)
    if not posts:
        return []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for post in posts:
        author = str(post.get("author") or "").strip()
        if author.lower() in SKIP_AUTHORS:
            continue
        grouped[author].append(post)
    hits = [_hit_from_posts(author, rows, job) for author, rows in grouped.items()]
    logger.info("reddit_search_hits count=%s", len(hits))
    return hits


def _job_query(job: dict[str, Any]) -> str:
    skills = job.get("requirements", {}).get("skills") or []
    parts = [str(job.get("title") or "")]
    parts.extend(str(skill) for skill in skills[:6])
    return " ".join(part for part in parts if part).strip() or "software engineer"


def _hit_from_posts(author: str, posts: list[dict[str, Any]], job: dict[str, Any]) -> dict[str, Any]:
    identifier = f"u/{author}"
    snippets: list[str] = []
    experience: list[str] = []
    projects: list[str] = []
    source_url = ""
    for post in posts:
        title = str(post.get("title") or "").strip()
        body = str(post.get("selftext") or post.get("body") or "").strip()
        permalink = _permalink(post)
        if permalink and not source_url:
            source_url = permalink
        if title:
            snippets.append(title)
            subreddit = str(post.get("subreddit") or "").strip()
            experience.append(f"r/{subreddit}: {title}" if subreddit else title)
        if body:
            snippets.append(body[:500])
        projects.extend(_project_links(post))
    text = "\n".join(snippets)
    required = [str(skill) for skill in (job.get("requirements", {}).get("skills") or [])]
    skills = _skills_in_text(required, text)
    technologies, gemini_skills, location = _gemini_extract(identifier, source_url, text)
    for skill in gemini_skills:
        if skill not in skills:
            skills.append(skill)
    evidence = RedditEvidence(
        source="Reddit",
        source_url=source_url,
        profile_identifier=identifier,
        professional_evidence=snippets[:12],
        skills=skills,
        technologies=technologies,
        projects=list(dict.fromkeys(projects)),
        relevant_experience=experience[:12],
        timestamp=utc_now(),
    )
    return {
        "id": f"reddit-{author.lower()}",
        "profile": {
            "name": identifier,
            "title": "Unverified Reddit handle",
            "source": "Reddit",
            "url": source_url,
            "skills": skills,
            "technologies": technologies,
            "experience_years": 0,
            "location": location,
            "resume_summary": "Public Reddit discussions only. This handle is not a verified candidate.",
            "identity_status": "unverified_reddit_handle",
            "reddit_evidence": evidence.model_dump(),
        },
    }


def _permalink(post: dict[str, Any]) -> str:
    permalink = str(post.get("permalink") or "").strip()
    if permalink.startswith("/"):
        return f"https://www.reddit.com{permalink}"
    url = str(post.get("url") or "").strip()
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    if host.endswith("reddit.com"):
        return url
    return permalink


def _project_links(post: dict[str, Any]) -> list[str]:
    found: list[str] = []
    candidates = [str(post.get("url") or "")]
    candidates.extend(URL_RE.findall(str(post.get("selftext") or "")))
    for raw in candidates:
        url = raw.rstrip(".,")
        host = (urlparse(url).hostname or "").lower().rstrip(".")
        if not host or host in REDDIT_HOSTS or host.endswith(".reddit.com"):
            continue
        found.append(url)
    return found


def _skills_in_text(required: list[str], text: str) -> list[str]:
    haystack = text.lower()
    haystack_keys = {canonical_skill(part) for part in re.split(r"\W+", haystack) if part}
    matched: list[str] = []
    seen: set[str] = set()
    for skill in required:
        label = str(skill or "").strip()
        if not label:
            continue
        key = canonical_skill(label)
        if not key or key in seen:
            continue
        if key in haystack or key in haystack_keys or label.lower() in haystack:
            seen.add(key)
            matched.append(label)
    return matched


def _gemini_extract(identifier: str, url: str, text: str) -> tuple[list[str], list[str], str]:
    if not gemini_configured() or not text.strip():
        return [], [], ""
    try:
        analysis = analyze_source("reddit", url or identifier, text)
    except Exception:
        logger.info("reddit_gemini_skipped")
        return [], [], ""
    technologies = [str(item) for item in (analysis.technologies or []) if item]
    skills = [str(item) for item in (analysis.skills or []) if item]
    return technologies, skills, str(analysis.location or "")
