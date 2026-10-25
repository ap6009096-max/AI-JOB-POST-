from __future__ import annotations

import math
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CandidateProfile, Embedding, Job
from app.db.repositories import EmbeddingRepository
from app.services.embedding_service import OWNER_CANDIDATE, OWNER_JOB, retrieve
from app.services.gemini_service import EMBEDDING_MODEL


def similar(
    session: Session,
    query_vector: list[float],
    owner_type: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    if not query_vector or limit <= 0:
        return []
    bind = session.get_bind()
    dialect = bind.dialect.name if bind is not None else ""
    if dialect == "postgresql":
        return _similar_pg(session, query_vector, owner_type, limit=limit)
    return _similar_python(session, query_vector, owner_type, limit=limit)


def similar_candidates_for_job(
    session: Session,
    job: Job,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    vector = _job_query_vector(session, job)
    if not vector:
        return []
    hits = similar(session, vector, OWNER_CANDIDATE, limit=limit)
    if not hits:
        return []
    profile_ids = [UUID(str(item["owner_id"])) for item in hits]
    profiles = {
        row.id: row
        for row in session.scalars(select(CandidateProfile).where(CandidateProfile.id.in_(profile_ids))).all()
    }
    results: list[dict[str, Any]] = []
    for item in hits:
        profile = profiles.get(UUID(str(item["owner_id"])))
        results.append(
            {
                **item,
                "candidate_id": str(profile.candidate_id) if profile is not None else "",
            }
        )
    return results


def similar_jobs_for_candidate(
    session: Session,
    profile: CandidateProfile,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    row = retrieve(session, profile.embedding_id) if profile.embedding_id else None
    vector = list(row.embedding) if row is not None else []
    if not vector:
        return []
    return similar(session, vector, OWNER_JOB, limit=limit)


def job_query_vector(session: Session, job: Job) -> list[float]:
    return _job_query_vector(session, job)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    return _cosine(left, right)


def _job_query_vector(session: Session, job: Job) -> list[float]:
    if job.embedding_id:
        row = retrieve(session, job.embedding_id)
        if row is not None:
            return list(row.embedding)
    row = EmbeddingRepository(session).get_by_owner(
        owner_type=OWNER_JOB, owner_id=job.id, model=EMBEDDING_MODEL
    )
    if row is None:
        return []
    return list(row.embedding)


def _similar_pg(session: Session, query_vector: list[float], owner_type: str, *, limit: int) -> list[dict[str, Any]]:
    from sqlalchemy import text

    literal = "[" + ",".join(str(float(value)) for value in query_vector) + "]"
    rows = session.execute(
        text(
            """
            SELECT id, owner_id, owner_type,
                   (1 - (embedding <=> CAST(:query AS vector))) AS score
            FROM embeddings
            WHERE owner_type = :owner_type
            ORDER BY embedding <=> CAST(:query AS vector)
            LIMIT :limit
            """
        ),
        {"query": literal, "owner_type": owner_type, "limit": limit},
    ).mappings()
    return [
        {
            "embedding_id": str(row["id"]),
            "owner_id": str(row["owner_id"]),
            "owner_type": row["owner_type"],
            "score": float(row["score"] or 0),
        }
        for row in rows
    ]


def _similar_python(
    session: Session, query_vector: list[float], owner_type: str, *, limit: int
) -> list[dict[str, Any]]:
    rows = list(session.scalars(select(Embedding).where(Embedding.owner_type == owner_type)))
    scored = [(_hit(row, _cosine(query_vector, list(row.embedding)))) for row in rows]
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]


def _hit(row: Embedding, score: float) -> dict[str, Any]:
    return {
        "embedding_id": str(row.id),
        "owner_id": str(row.owner_id),
        "owner_type": row.owner_type,
        "score": score,
    }


def _cosine(left: list[float], right: list[float]) -> float:
    size = min(len(left), len(right))
    if size == 0:
        return 0.0
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for index in range(size):
        a = float(left[index])
        b = float(right[index])
        dot += a * b
        left_norm += a * a
        right_norm += b * b
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return dot / math.sqrt(left_norm * right_norm)
