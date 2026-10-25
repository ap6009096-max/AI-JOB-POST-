from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Candidate, Job
from app.db.repositories import CandidateRepository
from app.services.candidates import compose_full_name
from app.services.comparison import SCORE_VERSION, SCORE_WEIGHTS, requirement_overlap, score_match
from app.services.gemini_service import generate_match_explanation, is_configured
from app.services.job_document import document_from_job
from app.services.matching import MatchingService
from app.services.privacy import strip_protected_disclosures
from app.services.vector_search import similar_candidates_for_job

RETRIEVAL_MIN = 50
RETRIEVAL_CAP = 200
PORTAL_STORE_LIMIT = 100
PORTAL_SOURCE = "AI Job Post Portal"

_PORTAL_REASON_LABELS = {
    "skills": "skills overlap with the job",
    "experience": "years of experience vs requirement",
    "projects": "project text vs job skills and tech",
    "education": "education vs job requirement",
    "technology": "technology overlap",
    "semantic": "embedding similarity",
    "location": "location fit",
    "salary": "salary and preference fit",
}


def list_eligible_candidates(session: Session) -> list[Candidate]:
    return [row for row in CandidateRepository(session).list_registered() if is_eligible(row)]


def is_eligible(candidate: Candidate) -> bool:
    if candidate.profile is None:
        return False
    user = candidate.user
    if user is None or user.role != "candidate" or user.status != "active":
        return False
    if candidate.status != "active":
        return False
    extras = dict(candidate.profile.extras or {})
    preferences = extras.get("preferences") if isinstance(extras.get("preferences"), dict) else {}
    return preferences.get("open_to_work") is not False


def portal_document(candidate: Candidate) -> dict[str, Any]:
    profile = candidate.profile
    extras = strip_protected_disclosures(dict(profile.extras or {})) if profile is not None else {}
    personal = extras.get("personal") if isinstance(extras.get("personal"), dict) else {}
    preferences = extras.get("preferences") if isinstance(extras.get("preferences"), dict) else {}
    master = extras.get("master_candidate") if isinstance(extras.get("master_candidate"), dict) else {}
    user = candidate.user
    name = ""
    if user is not None and user.full_name:
        name = user.full_name
    if not name:
        name = compose_full_name(personal)
    if not name:
        name = " ".join(
            part
            for part in [
                str(master.get("given_name") or "").strip(),
                str(master.get("family_name") or "").strip(),
            ]
            if part
        )
    skills = [row.skill for row in candidate.skills if row.skill]
    if not skills:
        skills = _named_values(master.get("skills"), "skill") or _named_values(master.get("skills"), "name")
    technologies = _named_values(extras.get("technologies"), "name")
    if not technologies:
        technologies = _named_values(master.get("technologies"), "name")
    experience_rows = _experience_rows(candidate, master)
    education_rows = _education_rows(candidate, master)
    project_rows = _project_rows(candidate, master)
    location = (profile.location if profile is not None else "") or str(master.get("city") or "")
    summary = (profile.summary if profile is not None else "") or str(master.get("summary") or "")
    document = {
        "id": str(candidate.id),
        "name": name,
        "title": (profile.headline if profile is not None else "") or str(master.get("current_role") or ""),
        "location": location,
        "skills": skills,
        "technologies": technologies,
        "experience_years": _experience_years(candidate, master),
        "experience": experience_rows,
        "education": education_rows,
        "projects": project_rows,
        "summary": summary,
        "resume_summary": summary,
        "salary_expectation": str(preferences.get("salary_expectation") or ""),
        "preferences": preferences,
    }
    return strip_protected_disclosures(document)


def list_portal_documents(session: Session) -> list[dict[str, Any]]:
    documents = [portal_document(row) for row in list_eligible_candidates(session)]
    documents.sort(key=lambda item: item.get("name") or "")
    return documents


def get_portal_document(session: Session, candidate_id: UUID) -> dict[str, Any] | None:
    candidate = CandidateRepository(session).get_registered(candidate_id)
    if candidate is None or candidate.profile is None:
        return None
    return portal_document(candidate)


def rank_portal_job(session: Session, job: Job) -> tuple[list[dict[str, Any]], Any]:
    store_limit = PORTAL_STORE_LIMIT
    job_json = strip_protected_disclosures(document_from_job(job))
    eligible = list_eligible_candidates(session)
    shortlisted, semantic_by_id = _retrieve_pool(session, job, eligible, store_limit)
    scored: list[dict[str, Any]] = []
    profiles: dict[str, dict[str, Any]] = {}
    required_skills = list(job_json.get("required_skills") or []) or list(
        (job_json.get("requirements") or {}).get("skills") or []
    )
    for candidate in shortlisted:
        profile = portal_document(candidate)
        profiles[str(candidate.id)] = profile
        match = score_match(job_json, profile, semantic=semantic_by_id.get(candidate.id, 0.0))
        parts = match["parts"]
        matched, missing = requirement_overlap(required_skills, list(profile.get("skills") or []))
        scored.append(
            {
                "candidate_id": str(candidate.id),
                "name": profile.get("name") or "",
                "title": profile.get("title") or "",
                "source": PORTAL_SOURCE,
                "location": profile.get("location") or "",
                "score": match["score"],
                "parts": parts,
                "matched_requirements": matched,
                "missing_requirements": missing,
                "calculation_version": match["version"],
                "narrative": None,
                "reasons": _portal_reasons(parts),
            }
        )
    scored.sort(key=lambda row: (-row["score"], row["name"]))
    limited = scored[:store_limit]
    use_gemini = True
    for index, row in enumerate(limited, start=1):
        row["rank"] = index
        narrative = (
            _match_narrative(
                job_json,
                profiles[row["candidate_id"]],
                {
                    "score": row["score"],
                    "parts": row["parts"],
                    "weights": dict(SCORE_WEIGHTS),
                    "version": SCORE_VERSION,
                },
            )
            if use_gemini
            else None
        )
        if use_gemini and narrative is None:
            use_gemini = False
        row["narrative"] = narrative
        if narrative:
            row["reasons"] = _reasons_from_narrative(narrative)
    run = MatchingService(session).persist_portal_run(job_id=job.id, limit=store_limit, results=limited)
    return limited, run


def _retrieve_pool(
    session: Session,
    job: Job,
    eligible: list[Candidate],
    limit: int,
) -> tuple[list[Candidate], dict[UUID, float]]:
    by_id = {row.id: row for row in eligible}
    pool_size = min(RETRIEVAL_CAP, max(RETRIEVAL_MIN, limit * 5))
    ordered_ids: list[UUID] = []
    semantic: dict[UUID, float] = {}
    if job.embedding_id is not None:
        for hit in similar_candidates_for_job(session, job, limit=pool_size):
            raw_id = hit.get("candidate_id") or ""
            try:
                candidate_id = UUID(str(raw_id))
            except ValueError:
                continue
            if candidate_id not in by_id or candidate_id in semantic:
                continue
            ordered_ids.append(candidate_id)
            semantic[candidate_id] = max(0.0, min(1.0, float(hit.get("score") or 0)))
            if len(ordered_ids) >= pool_size:
                break
    remaining = sorted(
        (row for row in eligible if row.id not in semantic),
        key=lambda row: (portal_document(row).get("name") or "", str(row.id)),
    )
    for row in remaining:
        if len(ordered_ids) >= pool_size:
            break
        ordered_ids.append(row.id)
    return [by_id[candidate_id] for candidate_id in ordered_ids if candidate_id in by_id], semantic


def _portal_reasons(parts: dict[str, float]) -> list[str]:
    ordered = sorted(parts.items(), key=lambda item: item[1], reverse=True)
    return [
        f"Ranking engine: {_PORTAL_REASON_LABELS.get(key, key)} ({value:.0%})"
        for key, value in ordered[:3]
        if key in _PORTAL_REASON_LABELS
    ]


def _reasons_from_narrative(narrative: dict[str, Any]) -> list[str]:
    recommendation = str(narrative.get("recommendation") or "").strip()
    if recommendation:
        return [recommendation]
    explanation = str(narrative.get("explanation") or "").strip()
    if explanation:
        first = explanation.split(".")[0].strip()
        return [first if first.endswith(".") else f"{first}."]
    return []


def _match_narrative(
    job_json: dict[str, Any],
    profile: dict[str, Any],
    scores: dict[str, Any],
) -> dict[str, Any] | None:
    if not is_configured():
        return None
    try:
        explanation = generate_match_explanation(job_json, profile, scores)
    except Exception:
        return None
    return {
        "explanation": explanation.explanation,
        "evidence": explanation.evidence,
        "strengths": list(explanation.strengths),
        "weaknesses": list(explanation.weaknesses),
        "recommendation": explanation.recommendation,
    }


def _named_values(value: object, key: str) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for item in value:
        if isinstance(item, dict):
            name = str(item.get(key) or item.get("name") or "").strip()
            if name:
                names.append(name)
        elif str(item).strip():
            names.append(str(item).strip())
    return names


def _experience_years(candidate: Candidate, master: dict[str, Any]) -> float:
    today = date.today()
    total_days = 0
    counted = False
    for row in candidate.experience:
        if row.start_date is None:
            continue
        counted = True
        end = row.end_date or today
        total_days += max((end - row.start_date).days, 0)
    if counted:
        return round(total_days / 365.25, 2)
    try:
        return float(master.get("experience_years") or 0)
    except (TypeError, ValueError):
        return 0.0


def _experience_rows(candidate: Candidate, master: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "company_name": row.company_name,
            "title": row.title,
            "description": row.description,
        }
        for row in candidate.experience
    ]
    if rows:
        return rows
    return [dict(item) for item in master.get("experience") or [] if isinstance(item, dict)]


def _education_rows(candidate: Candidate, master: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "school": row.school,
            "degree": row.degree,
            "field_of_study": row.field_of_study,
        }
        for row in candidate.education
    ]
    if rows:
        return rows
    return [dict(item) for item in master.get("education") or [] if isinstance(item, dict)]


def _project_rows(candidate: Candidate, master: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "name": row.name,
            "description": row.description,
        }
        for row in candidate.projects
    ]
    if rows:
        return rows
    return [dict(item) for item in master.get("projects") or [] if isinstance(item, dict)]
