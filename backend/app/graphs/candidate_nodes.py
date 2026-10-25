from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from langgraph.config import get_config
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import Candidate, CandidateSource
from app.graphs.candidate_state import CandidateGraphState
from app.schemas.candidate import MasterCandidate
from app.schemas.source import utc_now
from app.services.embedding_service import OWNER_CANDIDATE, cached_vector, candidate_embedding_text
from app.services.gemini_service import embed_text, is_configured
from app.services.profile_sync import apply_master_proposal
from app.services.resume_parse import ResumeParseError, analyze_resume_text, extract_text, normalize_parse_result
from app.services.resume_storage import ResumeStorageError, get_bytes
from app.services.source_service import analyze_url

logger = logging.getLogger(__name__)

SOURCE_OK = "ok"
NAMED_SOURCES = {"github", "linkedin", "portfolio"}


def load_candidate(state: CandidateGraphState) -> dict[str, Any]:
    candidate = _candidate()
    return {
        "candidate_id": str(candidate.id),
        "status": "running",
        **_done("load_candidate"),
    }


def load_resume(state: CandidateGraphState) -> dict[str, Any]:
    candidate = _candidate()
    resume = _resume_extras(candidate)
    text = str(resume.get("text") or "").strip()
    content_type = str(resume.get("content_type") or "")
    object_key = str(resume.get("object_key") or "")
    parse_result = resume.get("parse_result") if isinstance(resume.get("parse_result"), dict) else {}
    payload: dict[str, Any] = {
        "resume_content_type": content_type,
        "parse_result": parse_result or {},
        "resume_bytes": None,
        **_done("load_resume"),
    }
    if text:
        payload.update({"resume_present": True, "resume_text": text, "extraction_ok": True})
        return payload
    if object_key:
        try:
            data = get_bytes(object_key)
        except ResumeStorageError:
            return {
                **payload,
                "resume_present": False,
                "resume_text": "",
                "extraction_ok": False,
                "skipped": [
                    _skip("extract_document", "missing_resume"),
                    _skip("analyze_resume", "missing_resume"),
                ],
            }
        payload.update({"resume_present": True, "resume_bytes": data, "resume_text": ""})
        return payload
    return {
        **payload,
        "resume_present": False,
        "resume_text": "",
        "extraction_ok": False,
        "skipped": [
            _skip("extract_document", "missing_resume"),
            _skip("analyze_resume", "missing_resume"),
        ],
    }


def extract_document(state: CandidateGraphState) -> dict[str, Any]:
    existing = str(state.get("resume_text") or "").strip()
    if existing:
        return {"extraction_ok": True, "resume_text": existing, **_done("extract_document")}
    data = state.get("resume_bytes")
    content_type = str(state.get("resume_content_type") or "")
    if not data:
        return {
            "extraction_ok": False,
            "skipped": [_skip("extract_document", "extraction_failure"), _skip("analyze_resume", "extraction_failure")],
            **_done("extract_document"),
        }
    try:
        text = extract_text(data, content_type)
    except ResumeParseError as exc:
        logger.info("pipeline_extract_failed stage=%s", exc.stage)
        return {
            "extraction_ok": False,
            "resume_text": "",
            "errors": [_error("extract_document", "extraction_failure", str(exc))],
            "skipped": [_skip("analyze_resume", "extraction_failure")],
            **_done("extract_document"),
        }
    except Exception as exc:
        logger.exception("pipeline_extract_failed")
        return {
            "extraction_ok": False,
            "resume_text": "",
            "errors": [_error("extract_document", "extraction_failure", str(exc))],
            "skipped": [_skip("analyze_resume", "extraction_failure")],
            **_done("extract_document"),
        }
    if not str(text).strip():
        return {
            "extraction_ok": False,
            "resume_text": "",
            "skipped": [_skip("extract_document", "extraction_failure"), _skip("analyze_resume", "extraction_failure")],
            **_done("extract_document"),
        }
    return {"extraction_ok": True, "resume_text": text, **_done("extract_document")}


def analyze_resume(state: CandidateGraphState) -> dict[str, Any]:
    existing = state.get("parse_result") if isinstance(state.get("parse_result"), dict) else {}
    if _has_resume_evidence(existing):
        return {"parse_result": normalize_parse_result(existing), **_done("analyze_resume")}
    text = str(state.get("resume_text") or "")
    if not is_configured():
        return {
            "parse_result": normalize_parse_result(existing),
            "skipped": [_skip("analyze_resume", "ai_failure")],
            **_done("analyze_resume"),
        }
    try:
        parsed = analyze_resume_text(text)
    except ResumeParseError as exc:
        logger.info("pipeline_resume_ai_failed")
        return {
            "parse_result": normalize_parse_result(existing),
            "errors": [_error("analyze_resume", "ai_failure", str(exc))],
            "skipped": [_skip("analyze_resume", "ai_failure")],
            **_done("analyze_resume"),
        }
    return {"parse_result": parsed, **_done("analyze_resume")}


def analyze_github(state: CandidateGraphState) -> dict[str, Any]:
    return _analyze_named("github", "github")


def analyze_linkedin(state: CandidateGraphState) -> dict[str, Any]:
    return _analyze_named("linkedin", "linkedin")


def analyze_portfolio(state: CandidateGraphState) -> dict[str, Any]:
    return _analyze_named("portfolio", "portfolio")


def analyze_other_sources(state: CandidateGraphState) -> dict[str, Any]:
    candidate = _candidate()
    rows = [
        row
        for row in candidate.sources
        if (row.url or "").strip() and (row.source or "").strip().lower() not in NAMED_SOURCES
    ]
    results: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    if not rows:
        skipped.append(_skip("analyze_other_sources", "missing_url"))
    for row in rows:
        payload, skip = _run_source(row)
        results.append(payload)
        if skip:
            skipped.append(skip)
    update: dict[str, Any] = {"other_sources": results, **_done("analyze_other_sources")}
    if skipped:
        update["skipped"] = skipped
    return update


def merge_sources(state: CandidateGraphState) -> dict[str, Any]:
    parse_result = normalize_parse_result(state.get("parse_result") if isinstance(state.get("parse_result"), dict) else {})
    sources = _source_payloads(state)
    skills = _skill_dicts(parse_result.get("skills"))
    technologies = _tech_dicts(parse_result.get("technologies"))
    projects = list(parse_result.get("projects") or [])
    experience = list(parse_result.get("experience") or [])
    provenance: dict[str, list[str]] = {
        "skills": ["resume"] if skills else [],
        "technologies": ["resume"] if technologies else [],
        "projects": ["resume"] if projects else [],
        "experience": ["resume"] if experience else [],
    }
    for item in sources:
        analysis = item.get("analysis") if isinstance(item.get("analysis"), dict) else {}
        source_name = str(item.get("source") or "")
        extra_skills = _skill_dicts(analysis.get("skills"))
        extra_tech = _tech_dicts(analysis.get("technologies") or analysis.get("skills"))
        extra_projects = analysis.get("projects") if isinstance(analysis.get("projects"), list) else []
        if extra_skills:
            skills.extend(extra_skills)
            provenance.setdefault("skills", []).append(source_name)
        if extra_tech:
            technologies.extend(extra_tech)
            provenance.setdefault("technologies", []).append(source_name)
        if extra_projects:
            projects.extend([p for p in extra_projects if isinstance(p, dict)])
            provenance.setdefault("projects", []).append(source_name)
    merged = {
        **parse_result,
        "skills": skills,
        "technologies": technologies,
        "projects": projects,
        "experience": experience,
        "sources": sources,
        "provenance": provenance,
    }
    return {"merged": merged, **_done("merge_sources")}


def normalize_candidate(state: CandidateGraphState) -> dict[str, Any]:
    merged = state.get("merged") if isinstance(state.get("merged"), dict) else {}
    normalized = normalize_parse_result(merged)
    normalized["sources"] = merged.get("sources") if isinstance(merged.get("sources"), list) else []
    normalized["provenance"] = merged.get("provenance") if isinstance(merged.get("provenance"), dict) else {}
    normalized["skills"] = _skill_dicts(merged.get("skills"))
    normalized["technologies"] = _tech_dicts(merged.get("technologies"))
    normalized["projects"] = [item for item in (merged.get("projects") or []) if isinstance(item, dict)]
    normalized["experience"] = [item for item in (merged.get("experience") or []) if isinstance(item, dict)]
    return {"normalized": normalized, **_done("normalize_candidate")}


def deduplicate(state: CandidateGraphState) -> dict[str, Any]:
    normalized = dict(state.get("normalized") or {})
    skills, dropped_skills = _unique_named(normalized.get("skills") or [], "skill")
    technologies, dropped_tech = _unique_named(normalized.get("technologies") or [], "name")
    experience, dropped_exp = _unique_experience(normalized.get("experience") or [])
    normalized["skills"] = skills
    normalized["technologies"] = technologies
    normalized["experience"] = experience
    update: dict[str, Any] = {"normalized": normalized, **_done("deduplicate")}
    if dropped_skills or dropped_tech or dropped_exp:
        update["skipped"] = [_skip("deduplicate", "duplicate_information")]
    return update


def validate_candidate(state: CandidateGraphState) -> dict[str, Any]:
    normalized = dict(state.get("normalized") or {})
    sources = normalized.get("sources") if isinstance(normalized.get("sources"), list) else []
    cleaned = []
    for item in sources:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "")
        if url and not _http_url_ok(url):
            continue
        cleaned.append(item)
    normalized["sources"] = cleaned
    has_evidence = _has_resume_evidence(normalized) or any(
        str(item.get("fetch_status") or "") == SOURCE_OK for item in cleaned
    )
    if not has_evidence:
        reason = "validation_failure"
        return {
            "normalized": normalized,
            "validation_ok": False,
            "skipped": [
                _skip("create_master_candidate_json", reason),
                _skip("generate_candidate_embedding", reason),
            ],
            "errors": [_error("validate_candidate", reason, "No usable professional evidence")],
            **_done("validate_candidate"),
        }
    return {"normalized": normalized, "validation_ok": True, **_done("validate_candidate")}


def create_master_candidate_json(state: CandidateGraphState) -> dict[str, Any]:
    normalized = state.get("normalized") if isinstance(state.get("normalized"), dict) else {}
    master = MasterCandidate(
        given_name=str(normalized.get("given_name") or ""),
        middle_name=str(normalized.get("middle_name") or ""),
        family_name=str(normalized.get("family_name") or ""),
        current_role=str(normalized.get("current_role") or ""),
        summary=str(normalized.get("summary") or ""),
        city=str(normalized.get("city") or ""),
        country=str(normalized.get("country") or ""),
        skills=list(normalized.get("skills") or []),
        technologies=list(normalized.get("technologies") or []),
        experience=list(normalized.get("experience") or []),
        education=list(normalized.get("education") or []),
        projects=list(normalized.get("projects") or []),
        certifications=list(normalized.get("certifications") or []),
        achievements=list(normalized.get("achievements") or []),
        sources=list(normalized.get("sources") or []),
        provenance=dict(normalized.get("provenance") or {}),
        timestamp=utc_now(),
    ).model_dump()
    return {"master": master, **_done("create_master_candidate_json")}


def generate_candidate_embedding(state: CandidateGraphState) -> dict[str, Any]:
    master = state.get("master") if isinstance(state.get("master"), dict) else {}
    text = candidate_embedding_text(master)
    profile = _candidate().profile
    if profile is not None and text.strip():
        cached = cached_vector(
            _session(), owner_type=OWNER_CANDIDATE, owner_id=profile.id, text=text
        )
        if cached:
            return {"embedding_ok": True, "embedding": cached, **_done("generate_candidate_embedding")}
    if not text.strip() or not is_configured():
        return {
            "embedding_ok": False,
            "embedding": [],
            "skipped": [_skip("generate_candidate_embedding", "ai_failure")],
            **_done("generate_candidate_embedding"),
        }
    try:
        vector = embed_text(text)
    except Exception:
        logger.info("pipeline_embed_failed")
        return {
            "embedding_ok": False,
            "embedding": [],
            "errors": [_error("generate_candidate_embedding", "ai_failure", "Could not generate embedding")],
            "skipped": [_skip("generate_candidate_embedding", "ai_failure")],
            **_done("generate_candidate_embedding"),
        }
    return {"embedding_ok": True, "embedding": vector, **_done("generate_candidate_embedding")}


def save_profile(state: CandidateGraphState) -> dict[str, Any]:
    candidate = _candidate()
    session = _session()
    profile = candidate.profile
    if profile is None:
        return {
            "status": "failed",
            "errors": [_error("save_profile", "missing_profile", "Candidate profile is missing")],
            **_done("save_profile"),
        }
    skipped = list(state.get("skipped") or [])
    errors = list(state.get("errors") or [])
    if not state.get("validation_ok"):
        status = "validation_failed"
    elif errors:
        status = "completed_with_errors"
    else:
        status = "completed"
    pipeline = {
        "status": status,
        "current_node": "save_profile",
        "steps": list(state.get("steps") or []) + [_step("save_profile", "done")],
        "errors": errors,
        "skipped": skipped,
        "updated_at": utc_now(),
    }
    extras = dict(profile.extras or {})
    extras["candidate_pipeline"] = pipeline
    profile.extras = extras
    flag_modified(profile, "extras")
    master = state.get("master") if isinstance(state.get("master"), dict) else {}
    if master and state.get("validation_ok"):
        embedding = state.get("embedding") if isinstance(state.get("embedding"), list) else []
        apply_master_proposal(
            session,
            candidate,
            candidate.user_id,
            master,
            source="pipeline",
            embedding=list(embedding) if state.get("embedding_ok") and embedding else None,
        )
    return {"status": status, "current_node": "save_profile", "steps": [_step("save_profile", "done")]}


def route_after_resume(state: CandidateGraphState) -> str:
    if state.get("resume_present"):
        return "extract_document"
    return "analyze_github"


def route_after_extract(state: CandidateGraphState) -> str:
    if state.get("extraction_ok"):
        return "analyze_resume"
    return "analyze_github"


def route_after_validate(state: CandidateGraphState) -> str:
    if state.get("validation_ok"):
        return "create_master_candidate_json"
    return "save_profile"


def _candidate() -> Candidate:
    candidate = (get_config().get("configurable") or {}).get("candidate")
    if candidate is None:
        raise RuntimeError("candidate graph requires a candidate")
    return candidate


def _session():
    session = (get_config().get("configurable") or {}).get("session")
    if session is None:
        raise RuntimeError("candidate graph requires a database session")
    return session


def _resume_extras(candidate: Candidate) -> dict[str, Any]:
    extras = dict(candidate.profile.extras or {}) if candidate.profile else {}
    resume = extras.get("resume")
    return resume if isinstance(resume, dict) else {}


def _analyze_named(source: str, state_key: str) -> dict[str, Any]:
    candidate = _candidate()
    row = _named_source(candidate, source)
    if row is None or not (row.url or "").strip():
        return {
            state_key: {},
            "skipped": [_skip(f"analyze_{source}" if source != "portfolio" else "analyze_portfolio", "missing_url")],
            **_done(_analyze_node_name(source)),
        }
    payload, skip = _run_source(row)
    update: dict[str, Any] = {state_key: payload, **_done(_analyze_node_name(source))}
    if skip:
        update["skipped"] = [skip]
    return update


def _analyze_node_name(source: str) -> str:
    if source == "portfolio":
        return "analyze_portfolio"
    if source == "github":
        return "analyze_github"
    if source == "linkedin":
        return "analyze_linkedin"
    return "analyze_other_sources"


def _named_source(candidate: Candidate, source: str) -> CandidateSource | None:
    for row in candidate.sources:
        if (row.source or "").strip().lower() == source:
            return row
    return None


def _run_source(row: CandidateSource) -> tuple[dict[str, Any], dict[str, str] | None]:
    url = (row.url or "").strip()
    node = _analyze_node_name((row.source or "").strip().lower())
    if not _http_url_ok(url):
        payload = {"source": row.source, "url": url, "fetch_status": "skipped_invalid_url", "skip_reason": "http_https_required"}
        return payload, _skip(node, "invalid_url")
    result = analyze_url(row.source, url)
    extras = dict(row.extras or {})
    extras.update(result.to_extras())
    row.extras = extras
    flag_modified(row, "extras")
    payload = {
        "source": row.source,
        "url": url,
        "fetch_status": result.fetch_status,
        "skip_reason": result.skip_reason,
        "evidence": result.evidence,
        "analysis": result.analysis,
        "provenance": result.provenance,
    }
    if result.fetch_status != SOURCE_OK:
        reason = "invalid_url" if "invalid_url" in (result.fetch_status or "") else "source_failure"
        return payload, _skip(node, reason)
    return payload, None


def _source_payloads(state: CandidateGraphState) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key in ("github", "linkedin", "portfolio"):
        value = state.get(key)
        if isinstance(value, dict) and value:
            items.append(value)
    others = state.get("other_sources")
    if isinstance(others, list):
        items.extend(item for item in others if isinstance(item, dict))
    return items


def _skill_dicts(value: object) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return items
    for raw in value:
        if isinstance(raw, dict):
            name = str(raw.get("skill") or raw.get("name") or "").strip()
            if name:
                items.append({"skill": name, "years": raw.get("years")})
        elif isinstance(raw, str) and raw.strip():
            items.append({"skill": raw.strip(), "years": None})
    return items


def _tech_dicts(value: object) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return items
    for raw in value:
        if isinstance(raw, dict):
            name = str(raw.get("name") or raw.get("skill") or "").strip()
            if name:
                items.append({"name": name, "years": raw.get("years")})
        elif isinstance(raw, str) and raw.strip():
            items.append({"name": raw.strip(), "years": None})
    return items


def _unique_named(items: list, key: str) -> tuple[list[dict[str, Any]], int]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    dropped = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get(key) or "").strip().lower()
        if not name:
            continue
        if name in seen:
            dropped += 1
            continue
        seen.add(name)
        unique.append(item)
    return unique, dropped


def _unique_experience(items: list) -> tuple[list[dict[str, Any]], int]:
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    dropped = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        key = (str(item.get("title") or "").strip().lower(), str(item.get("company_name") or "").strip().lower())
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        unique.append(item)
    return unique, dropped


def _has_resume_evidence(parse: dict[str, Any]) -> bool:
    if str(parse.get("summary") or "").strip():
        return True
    if str(parse.get("given_name") or "").strip() or str(parse.get("family_name") or "").strip():
        return True
    for key in ("skills", "experience", "projects"):
        value = parse.get(key)
        if isinstance(value, list) and value:
            return True
    return False


def _http_url_ok(url: str) -> bool:
    if not url.strip():
        return True
    parsed = urlparse(url.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def _done(node: str) -> dict[str, Any]:
    return {"current_node": node, "steps": [_step(node, "done")]}


def _step(node: str, status: str) -> dict[str, str]:
    return {"node": node, "status": status, "at": utc_now()}


def _skip(node: str, reason: str) -> dict[str, str]:
    return {"node": node, "reason": reason}


def _error(node: str, code: str, message: str) -> dict[str, str]:
    return {"node": node, "code": code, "message": message}
