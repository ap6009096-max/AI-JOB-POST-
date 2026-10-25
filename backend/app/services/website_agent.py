from __future__ import annotations

import logging

from app.schemas.source import SourceAgentResult, utc_now
from app.services.gemini_service import analyze_portfolio_page, is_configured
from app.services.source_fetch import fetch_public, html_to_text

logger = logging.getLogger(__name__)


def analyze(url: str) -> SourceAgentResult:
    fetched = fetch_public(url)
    if not fetched.ok:
        return SourceAgentResult(
            url=url,
            analyzed_at=utc_now(),
            provenance="public_http",
            fetch_status=fetched.fetch_status or "failed",
            skip_reason=fetched.skip_reason,
        )
    text = html_to_text(fetched.body)
    evidence = {
        "url": str(fetched.url or url),
        "content_type": fetched.content_type,
        "text_excerpt": text[:4000],
    }
    analysis = _website_analysis(str(fetched.url or url), text)
    return SourceAgentResult(
        url=url,
        analyzed_at=utc_now(),
        provenance="public_http",
        fetch_status="ok",
        evidence=evidence,
        analysis=analysis,
    )


def _website_analysis(url: str, text: str) -> dict:
    if not is_configured() or not text.strip():
        return {}
    try:
        return analyze_portfolio_page(url, text).model_dump()
    except Exception:
        logger.info("website_gemini_skipped")
        return {}
