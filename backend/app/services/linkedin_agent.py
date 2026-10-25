from __future__ import annotations

from urllib.parse import urlparse

from app.schemas.source import SourceAgentResult, utc_now
from app.services.source_fetch import is_linkedin_host


def analyze(url: str) -> SourceAgentResult:
    host = urlparse((url or "").strip()).hostname
    skip = "linkedin_requires_authorized_api"
    if url and not is_linkedin_host(host):
        skip = "linkedin_url_required"
    return SourceAgentResult(
        url=url,
        analyzed_at=utc_now(),
        provenance="candidate_provided",
        fetch_status="skipped_linkedin_policy",
        skip_reason=skip,
        evidence={"url": url, "submitted_at": utc_now()},
        analysis={},
    )
