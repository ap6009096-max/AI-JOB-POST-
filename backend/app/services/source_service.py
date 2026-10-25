from __future__ import annotations

import logging
from urllib.parse import urlparse

from sqlalchemy.orm import object_session
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import Candidate, CandidateSource
from app.schemas.source import SourceAgentResult
from app.services import github_agent, linkedin_agent, portfolio_agent, website_agent
from app.services.profile_sync import apply_source_update
from app.services.source_fetch import is_github_host, is_linkedin_host

logger = logging.getLogger(__name__)


def analyze_candidate_sources(candidate: Candidate) -> list[dict]:
    rows = [row for row in candidate.sources if (row.url or "").strip()]
    payloads: list[dict] = []
    session = object_session(candidate)
    for row in rows:
        result = analyze_url(row.source, row.url or "")
        if session is not None:
            apply_source_update(session, candidate, candidate.user_id, row, result)
        else:
            extras = dict(row.extras or {})
            extras.update(result.to_extras())
            row.extras = extras
            flag_modified(row, "extras")
        logger.info(
            "source_analyzed source=%s status=%s provenance=%s",
            row.source,
            result.fetch_status,
            result.provenance,
        )
        payloads.append(link_payload(row))
    return payloads


def analyze_url(source: str, url: str) -> SourceAgentResult:
    host = urlparse((url or "").strip()).hostname
    if is_linkedin_host(host) or (source or "").strip().lower() == "linkedin":
        return linkedin_agent.analyze(url)
    if is_github_host(host) or (source or "").strip().lower() == "github":
        return github_agent.analyze(url)
    if (source or "").strip().lower() == "portfolio":
        return portfolio_agent.analyze(url)
    return website_agent.analyze(url)


def link_payload(row: CandidateSource) -> dict:
    extras = row.extras if isinstance(row.extras, dict) else {}
    analysis = None
    if extras.get("analyzed_at") or extras.get("fetch_status"):
        analysis = {
            "url": extras.get("url") or row.url or "",
            "analyzed_at": extras.get("analyzed_at") or "",
            "provenance": extras.get("provenance") or "",
            "fetch_status": extras.get("fetch_status") or "",
            "skip_reason": extras.get("skip_reason") or "",
            "evidence": extras.get("evidence") if isinstance(extras.get("evidence"), dict) else {},
            "analysis": extras.get("analysis") if isinstance(extras.get("analysis"), dict) else {},
        }
    return {
        "id": row.id,
        "source": row.source,
        "url": row.url,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "analysis": analysis,
    }


def _iso(value: object) -> str:
    if value is None:
        return ""
    iso = getattr(value, "isoformat", None)
    return iso() if callable(iso) else str(value)
