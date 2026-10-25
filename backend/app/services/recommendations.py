from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Candidate, Job
from app.services.comparison import SCORE_WEIGHTS, requirement_overlap, score_match
from app.services.job_document import document_from_job
from app.services.portal_ranking import portal_document
from app.services.privacy import strip_protected_disclosures
from app.services.vector_search import similar_jobs_for_candidate

RECOMMENDATION_LIMIT = 20


def list_job_recommendations(session: Session, candidate: Candidate, *, limit: int = RECOMMENDATION_LIMIT) -> list[dict[str, Any]]:
    profile = candidate.profile
    if profile is None:
        return []
    jobs = list(session.scalars(select(Job).where(Job.status == "open")))
    if not jobs:
        return []
    semantic: dict[UUID, float] = {}
    ordered_ids: list[UUID] = []
    if profile.embedding_id:
        for hit in similar_jobs_for_candidate(session, profile, limit=max(limit * 3, 30)):
            try:
                job_id = UUID(str(hit.get("owner_id") or ""))
            except ValueError:
                continue
            if job_id in semantic:
                continue
            semantic[job_id] = max(0.0, min(1.0, float(hit.get("score") or 0)))
            ordered_ids.append(job_id)
    by_id = {row.id: row for row in jobs}
    ranked_jobs: list[Job] = [by_id[job_id] for job_id in ordered_ids if job_id in by_id]
    for row in jobs:
        if row.id not in semantic:
            ranked_jobs.append(row)
    candidate_doc = portal_document(candidate)
    scored: list[dict[str, Any]] = []
    for job in ranked_jobs:
        job_json = strip_protected_disclosures(document_from_job(job))
        match = score_match(job_json, candidate_doc, semantic=semantic.get(job.id, 0.0))
        required = list(job_json.get("required_skills") or []) or list(
            (job_json.get("requirements") or {}).get("skills") or []
        )
        matched, missing = requirement_overlap(required, list(candidate_doc.get("skills") or []))
        scored.append(
            {
                "job_id": str(job.id),
                "title": job.title,
                "location": job.location or "",
                "company_id": str(job.company_id),
                "score": match["score"],
                "parts": match["parts"],
                "matched_requirements": matched,
                "missing_requirements": missing,
                "calculation_version": match["version"],
                "weights": dict(SCORE_WEIGHTS),
            }
        )
    scored.sort(key=lambda row: (-row["score"], row["title"]))
    limited = scored[:limit]
    for index, row in enumerate(limited, start=1):
        row["rank"] = index
    return limited
