from __future__ import annotations

from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy.orm import Session

from app.data.store import store
from app.db.models import Job
from app.services import github_agent, linkedin_agent, portfolio_agent, reddit_agent, website_agent
from app.services.comparison import SCORE_VERSION, SCORE_WEIGHTS, requirement_overlap, score_match
from app.services.embedding_service import internet_embedding_text
from app.services.gemini_service import embed_text, generate_match_explanation, is_configured
from app.services.job_document import document_from_job
from app.services.matching import MatchingService
from app.services.privacy import strip_protected_disclosures
from app.services.reddit_service import REDDIT_HOSTS, search_for_job
from app.services.source_fetch import is_github_host, is_linkedin_host
from app.services.sourcing import SourcingService
from app.services.vector_search import cosine_similarity, job_query_vector

INTERNET_STORE_LIMIT = 100
PERSONAL_FETCH_LIMIT = 5


def search_all_sources(session: Session, job: Job) -> dict[str, Any]:
    job_json = document_from_job(job)
    query_text = _job_query(job_json)
    sourcing = SourcingService(session)
    run = sourcing.create(
        job_id=job.id,
        status="running",
        query={"text": query_text, "title": job_json.get("title") or "", "skills": _job_skills(job_json)},
    )
    skipped: list[dict[str, str]] = []
    sources: list[str] = []
    hits: list[dict[str, Any]] = []

    linkedin = linkedin_agent.analyze("")
    skipped.append(
        {
            "source": "LinkedIn",
            "reason": linkedin.skip_reason or "linkedin_requires_authorized_api",
        }
    )

    github_hits, github_skip = _collect_github(query_text)
    if github_skip:
        skipped.append({"source": "GitHub", "reason": github_skip})
    else:
        sources.append("GitHub")
        hits.extend(github_hits)

    if not reddit_agent.is_configured():
        skipped.append({"source": "Reddit", "reason": "reddit_unconfigured"})
    else:
        sources.append("Reddit")
        hits.extend(search_for_job(job_json))

    personal_hits, personal_skips = _collect_personal_sites(hits)
    skipped.extend(personal_skips)
    if personal_hits:
        for hit in personal_hits:
            name = str((hit.get("profile") or {}).get("source") or "Portfolio")
            if name not in sources:
                sources.append(name)
        hits.extend(personal_hits)

    unique = _dedupe(hits)
    live = _persist_live_hits(sourcing, run.id, unique)
    used_seed_fallback = not live
    if used_seed_fallback:
        candidates = list(store.list_external())
    else:
        candidates = live

    completed_query = {
        "text": query_text,
        "title": job_json.get("title") or "",
        "skills": _job_skills(job_json),
        "skipped": skipped,
        "sources": sources,
        "used_seed_fallback": used_seed_fallback,
        "live_hits": len(live),
    }
    sourcing.complete(run, query=completed_query)
    return {
        "candidates": candidates,
        "skipped": skipped,
        "sources": sources,
        "sourcing_run_id": str(run.id),
        "used_seed_fallback": used_seed_fallback,
    }


def rank_internet_job(session: Session, job: Job) -> tuple[list[dict[str, Any]], Any]:
    sourced = search_all_sources(session, job)
    job_json = document_from_job(job)
    results = score_internet_candidates(
        job_json,
        sourced["candidates"],
        INTERNET_STORE_LIMIT,
        job_vector=job_query_vector(session, job),
    )
    run = MatchingService(session).persist_internet_run(
        job_id=job.id,
        limit=INTERNET_STORE_LIMIT,
        results=results,
        extra_params={
            "skipped": sourced["skipped"],
            "sources": sourced["sources"],
            "sourcing_run_id": sourced["sourcing_run_id"],
            "used_seed_fallback": sourced["used_seed_fallback"],
        },
    )
    return results, run


def _job_skills(job: dict[str, Any]) -> list[str]:
    required = job.get("required_skills") or []
    if required:
        return [str(skill) for skill in required]
    return [str(skill) for skill in (job.get("requirements", {}).get("skills") or [])]


def _job_query(job: dict[str, Any]) -> str:
    parts = [str(job.get("title") or "")]
    parts.extend(_job_skills(job)[:6])
    return " ".join(part for part in parts if part).strip() or "software engineer"


def _collect_github(query: str) -> tuple[list[dict[str, Any]], str | None]:
    logins, skip = github_agent.search_users(query)
    if skip:
        return [], skip
    hits: list[dict[str, Any]] = []
    for login in logins:
        analyzed = github_agent.analyze(f"https://github.com/{login}")
        if analyzed.fetch_status != "ok":
            continue
        hits.append(_github_hit(login, analyzed))
    return hits, None


def _github_hit(login: str, analyzed: Any) -> dict[str, Any]:
    evidence = dict(analyzed.evidence or {})
    profile = evidence.get("profile") if isinstance(evidence.get("profile"), dict) else {}
    analysis = dict(analyzed.analysis or {})
    skills = [str(skill) for skill in (analysis.get("skills") or evidence.get("languages") or []) if skill]
    technologies = [str(item) for item in (analysis.get("technologies") or evidence.get("languages") or []) if item]
    bio = str(profile.get("bio") or "")
    name = str(profile.get("name") or login)
    location = str(analysis.get("location") or profile.get("location") or "")
    return {
        "id": f"github-{login.lower()}",
        "profile": {
            "name": name,
            "title": str(analysis.get("title") or bio or "GitHub developer")[:80],
            "source": "GitHub",
            "url": f"https://github.com/{login}",
            "skills": skills,
            "technologies": technologies,
            "experience_years": 0,
            "location": location,
            "resume_summary": bio or str(analysis.get("summary") or ""),
        },
        "_evidence": {
            "kind": "github",
            "body": {"login": login, "evidence": evidence, "analysis": analysis},
        },
        "_blog": str(profile.get("blog") or ""),
    }


def _collect_personal_sites(hits: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    urls: list[str] = []
    for hit in hits:
        profile = hit.get("profile") or {}
        source = str(profile.get("source") or "")
        if source == "GitHub":
            urls.extend(_personal_urls(str(hit.get("_blog") or "")))
        if source == "Reddit":
            evidence = profile.get("reddit_evidence") if isinstance(profile.get("reddit_evidence"), dict) else {}
            projects = evidence.get("projects") or []
            if isinstance(projects, list):
                for project in projects:
                    urls.extend(_personal_urls(str(project)))
    unique_urls = list(dict.fromkeys(urls))[:PERSONAL_FETCH_LIMIT]
    collected: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for url in unique_urls:
        is_site = _looks_like_website(url)
        source_name = "Website" if is_site else "Portfolio"
        agent = website_agent if is_site else portfolio_agent
        analyzed = agent.analyze(url)
        if analyzed.fetch_status != "ok":
            skipped.append(
                {
                    "source": source_name,
                    "reason": analyzed.skip_reason or analyzed.fetch_status or "fetch_failed",
                }
            )
            continue
        collected.append(_personal_hit(url, analyzed, source=source_name))
    return collected, skipped


def _personal_hit(url: str, analyzed: Any, *, source: str) -> dict[str, Any]:
    analysis = dict(analyzed.analysis or {})
    evidence = dict(analyzed.evidence or {})
    skills = [str(skill) for skill in (analysis.get("skills") or []) if skill]
    technologies = [str(item) for item in (analysis.get("technologies") or []) if item]
    name = str(analysis.get("name") or analysis.get("display_name") or urlparse(url).hostname or "Personal site")
    summary = str(analysis.get("summary") or evidence.get("text_excerpt") or "")[:500]
    kind = "website" if source == "Website" else "portfolio"
    return {
        "id": f"{kind}-{_canonical_url(url)}",
        "profile": {
            "name": name,
            "title": str(analysis.get("title") or "Personal site"),
            "source": source,
            "url": url,
            "skills": skills,
            "technologies": technologies,
            "experience_years": 0,
            "location": str(analysis.get("location") or ""),
            "resume_summary": summary,
        },
        "_evidence": {
            "kind": kind,
            "body": {"url": url, "evidence": evidence, "analysis": analysis},
        },
    }


def _personal_urls(raw: str) -> list[str]:
    url = _absolute_http_url(raw)
    if url is None or not _is_permitted_personal_url(url):
        return []
    return [url]


def _absolute_http_url(raw: str) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None
    if text.startswith("//"):
        text = "https:" + text
    elif "://" not in text:
        text = "https://" + text
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    return text


def _is_permitted_personal_url(url: str) -> bool:
    host = urlparse(url).hostname
    if is_linkedin_host(host) or is_github_host(host):
        return False
    hostname = (host or "").lower().rstrip(".")
    if hostname in REDDIT_HOSTS or hostname.endswith(".reddit.com"):
        return False
    return True


def _looks_like_website(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host.startswith("www.") or host.count(".") >= 2


def _dedupe(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hit in hits:
        key = _dedupe_key(hit)
        if key in seen:
            continue
        seen.add(key)
        unique.append(hit)
    return unique


def _dedupe_key(hit: dict[str, Any]) -> str:
    profile = hit.get("profile") or {}
    source = str(profile.get("source") or "").lower()
    url = str(profile.get("url") or "")
    name = str(profile.get("name") or "").strip().lower()
    if source == "github":
        login = github_agent.github_login(url) or name
        return f"github:{login.lower()}"
    if source == "reddit":
        return f"reddit:{name.removeprefix('u/')}"
    canonical = _canonical_url(url)
    if canonical:
        return f"url:{canonical}"
    return f"{source}:{name}"


def _canonical_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    path = (parsed.path or "").rstrip("/").lower()
    return f"{host}{path}"


def _persist_live_hits(sourcing: SourcingService, run_id: UUID, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    persisted: list[dict[str, Any]] = []
    for hit in hits:
        profile = dict(hit.get("profile") or {})
        row = sourcing.create_external_candidate(
            sourcing_run_id=run_id,
            source=str(profile.get("source") or "Internet"),
            url=profile.get("url"),
            display_name=str(profile.get("name") or ""),
            payload=profile,
        )
        evidence = hit.get("_evidence") if isinstance(hit.get("_evidence"), dict) else None
        if evidence:
            sourcing.create_evidence(
                external_candidate_id=row.id,
                kind=str(evidence.get("kind") or "source"),
                body=dict(evidence.get("body") or {}),
            )
        persisted.append({"id": str(row.id), "profile": {**profile, "id": str(row.id)}})
    return persisted


DISPLAY_PARTS = ("projects", "education", "technology", "semantic")
HIGH_FIT = 0.6
LOW_FIT = 0.4


def score_internet_candidates(
    job: dict[str, Any],
    candidates: list[dict[str, Any]],
    limit: int,
    *,
    job_vector: list[float] | None = None,
) -> list[dict[str, Any]]:
    job_json = strip_protected_disclosures(job)
    required = _job_skills(job_json)
    scored: list[dict[str, Any]] = []
    profiles: dict[str, dict[str, Any]] = {}
    semantic_cache: dict[str, float] = {}
    for candidate in candidates:
        profile = strip_protected_disclosures(dict(candidate.get("profile") or {}))
        candidate_id = str(candidate.get("id") or profile.get("id") or "")
        profiles[candidate_id] = profile
        match = score_match(
            job_json,
            profile,
            semantic=_profile_semantic(profile, job_vector, cache=semantic_cache),
        )
        parts = match["parts"]
        matched, missing = requirement_overlap(required, list(profile.get("skills") or []))
        scored.append(
            {
                "candidate_id": candidate_id,
                "name": profile.get("name") or "",
                "title": profile.get("title") or "",
                "source": profile.get("source") or "Internet",
                "identity_status": profile.get("identity_status"),
                "location": profile.get("location") or "",
                "url": str(profile.get("url") or ""),
                "score": match["score"],
                "parts": parts,
                "matched_requirements": matched,
                "missing_requirements": missing,
                "calculation_version": match["version"],
                "confidence": match["score"],
                "narrative": None,
                "reasons": _internet_reasons(parts),
            }
        )
    scored.sort(key=lambda row: (-row["score"], row["name"]))
    limited = scored[:limit]
    use_gemini = True
    for index, row in enumerate(limited, start=1):
        row["rank"] = index
        narrative = _match_narrative(job_json, profiles.get(row["candidate_id"]) or {}, row) if use_gemini else None
        if use_gemini and narrative is None:
            use_gemini = False
        if narrative:
            row["narrative"] = narrative
            explanation = str(narrative.get("explanation") or "").strip()
            if explanation:
                first = explanation.split(".")[0].strip()
                row["reasons"] = [first if first.endswith(".") else f"{first}."]
        else:
            row["narrative"] = _internet_narrative(profiles.get(row["candidate_id"]) or {}, row)
    return limited


def _internet_reasons(parts: dict[str, float]) -> list[str]:
    labels = {
        "skills": "skills overlap with the job",
        "experience": "years of experience vs requirement",
        "projects": "project text vs job skills and tech",
        "education": "education vs job requirement",
        "technology": "technology overlap",
        "semantic": "embedding similarity",
    }
    ordered = sorted(parts.items(), key=lambda item: item[1], reverse=True)
    return [
        f"Ranking engine: {labels.get(key, key)} ({value:.0%})"
        for key, value in ordered[:3]
        if key in labels
    ]


def _match_narrative(job_json: dict[str, Any], profile: dict[str, Any], row: dict[str, Any]) -> dict[str, Any] | None:
    if not is_configured():
        return None
    try:
        explanation = generate_match_explanation(
            job_json,
            profile,
            {
                "score": row["score"],
                "parts": row["parts"],
                "weights": dict(SCORE_WEIGHTS),
                "version": SCORE_VERSION,
            },
        )
    except Exception:
        return None
    return {
        "explanation": explanation.explanation,
        "evidence": explanation.evidence,
        "strengths": list(explanation.strengths),
        "weaknesses": list(explanation.weaknesses),
        "recommendation": explanation.recommendation,
    }


def _enrich_internet_results(
    job: dict[str, Any],
    candidates: list[dict[str, Any]],
    results: list[dict[str, Any]],
    *,
    job_vector: list[float] | None = None,
) -> list[dict[str, Any]]:
    profiles = {str(item.get("id")): dict(item.get("profile") or {}) for item in candidates}
    required = _job_skills(job)
    cache: dict[str, float] = {}
    for row in results:
        profile = strip_protected_disclosures(profiles.get(str(row.get("candidate_id"))) or {})
        match = score_match(
            strip_protected_disclosures(job),
            profile,
            semantic=_profile_semantic(profile, job_vector, cache=cache),
        )
        stub_parts = dict(row.get("parts") or {})
        display_parts = {key: float(match["parts"].get(key) or 0.0) for key in DISPLAY_PARTS}
        row["parts"] = {**stub_parts, **display_parts}
        matched, missing = requirement_overlap(required, list(profile.get("skills") or []))
        row["matched_requirements"] = matched
        row["missing_requirements"] = missing
        row["url"] = str(profile.get("url") or "")
        row["confidence"] = float(row.get("score") or 0.0)
        row["narrative"] = _internet_narrative(profile, row)
        row["calculation_version"] = str(match.get("version") or "")
    return results


def _profile_semantic(
    profile: dict[str, Any],
    job_vector: list[float] | None,
    *,
    cache: dict[str, float] | None = None,
) -> float:
    if not job_vector:
        return 0.0
    snippet = internet_embedding_text(profile)
    if not snippet.strip():
        return 0.0
    if cache is not None and snippet in cache:
        return cache[snippet]
    try:
        vector = embed_text(snippet)
        score = max(0.0, min(1.0, cosine_similarity(job_vector, vector)))
    except Exception:
        score = 0.0
    if cache is not None:
        cache[snippet] = score
    return score


def _internet_narrative(profile: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    matched = [str(item) for item in (row.get("matched_requirements") or []) if item]
    missing = [str(item) for item in (row.get("missing_requirements") or []) if item]
    parts = dict(row.get("parts") or {})
    strengths = list(matched)
    for key in ("skills", "experience", "projects", "education", "technology"):
        if float(parts.get(key) or 0) >= HIGH_FIT:
            label = f"Strong {key} fit"
            if label not in strengths:
                strengths.append(label)
    weaknesses = list(missing)
    for key in ("skills", "experience", "projects", "education"):
        if float(parts.get(key) or 0) < LOW_FIT:
            label = f"Low {key} overlap"
            if label not in weaknesses:
                weaknesses.append(label)
    evidence = str(profile.get("resume_summary") or "").strip()
    reddit = profile.get("reddit_evidence") if isinstance(profile.get("reddit_evidence"), dict) else {}
    snippets = reddit.get("professional_evidence") or []
    if not evidence and isinstance(snippets, list):
        evidence = "; ".join(str(item) for item in snippets[:3] if item)
    url = str(profile.get("url") or row.get("url") or "").strip()
    if url and evidence:
        evidence = f"{evidence} Source: {url}"
    elif url:
        evidence = url
    reasons = list(row.get("reasons") or [])
    return {
        "explanation": reasons[0] if reasons else "",
        "evidence": evidence,
        "strengths": strengths[:8],
        "weaknesses": weaknesses[:8],
        "recommendation": "",
    }
