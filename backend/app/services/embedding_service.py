from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import CandidateProfile, Embedding, Job
from app.db.repositories import EmbeddingRepository
from app.services.gemini_service import EMBEDDING_MODEL, embed_text, is_configured
from app.services.job_document import document_from_job
from app.services.privacy import strip_protected_disclosures

logger = logging.getLogger(__name__)

OWNER_CANDIDATE = "candidate_profile"
OWNER_JOB = "job"


@dataclass
class EmbeddingResult:
    row: Embedding | None
    cached: bool = False
    skipped: bool = False


def candidate_embedding_text(master: dict[str, Any] | None) -> str:
    payload = strip_protected_disclosures(master if isinstance(master, dict) else {})
    sections = [
        _section("Skills", _named_values(payload.get("skills"), "skill")),
        _section(
            "Relevant Experience",
            [
                " ".join(
                    part
                    for part in (
                        str(item.get("title") or "").strip(),
                        str(item.get("company_name") or "").strip(),
                        str(item.get("description") or "").strip(),
                    )
                    if part
                )
                for item in _dicts(payload.get("experience"))
            ],
        ),
        _section(
            "Projects",
            [
                " ".join(
                    part
                    for part in (
                        str(item.get("name") or "").strip(),
                        str(item.get("description") or "").strip(),
                    )
                    if part
                )
                for item in _dicts(payload.get("projects"))
            ],
        ),
        _section("Technologies", _named_values(payload.get("technologies"), "name")),
        _section(
            "Education",
            [
                " ".join(
                    part
                    for part in (
                        str(item.get("school") or "").strip(),
                        str(item.get("degree") or "").strip(),
                        str(item.get("field_of_study") or "").strip(),
                    )
                    if part
                )
                for item in _dicts(payload.get("education"))
            ],
        ),
        _section("Professional Summary", [str(payload.get("summary") or "").strip()]),
    ]
    return "\n".join(section for section in sections if section).strip()


def internet_embedding_text(profile: dict[str, Any] | None) -> str:
    payload = strip_protected_disclosures(profile if isinstance(profile, dict) else {})
    sections = [
        _section("Title", [str(payload.get("title") or "").strip()]),
        _section("Skills", _string_list(payload.get("skills"))),
        _section("Technologies", _string_list(payload.get("technologies"))),
        _section(
            "Professional Summary",
            [str(payload.get("resume_summary") or payload.get("summary") or "").strip()],
        ),
    ]
    return "\n".join(section for section in sections if section).strip()


def job_embedding_text(job: dict[str, Any] | Job | None) -> str:
    if isinstance(job, Job):
        payload = document_from_job(job)
    elif isinstance(job, dict):
        payload = job
    else:
        payload = {}
    payload = strip_protected_disclosures(payload)
    sections = [
        _section("Job Title", [str(payload.get("title") or "").strip()]),
        _section("Description", [str(payload.get("description") or "").strip()]),
        _section("Required Skills", _string_list(payload.get("required_skills"))),
        _section("Preferred Skills", _string_list(payload.get("preferred_skills"))),
        _section("Responsibilities", _string_list(payload.get("responsibilities"))),
        _section("Technologies", _string_list(payload.get("technologies"))),
    ]
    return "\n".join(section for section in sections if section).strip()


def content_hash(text: str, *, model: str = EMBEDDING_MODEL) -> str:
    return hashlib.sha256(f"{model}\n{text}".encode()).hexdigest()


def retrieve(session: Session, embedding_id: UUID) -> Embedding | None:
    return EmbeddingRepository(session).get(embedding_id)


def cached_vector(session: Session, *, owner_type: str, owner_id: UUID, text: str) -> list[float] | None:
    if not text.strip():
        return None
    existing = EmbeddingRepository(session).get_by_owner(
        owner_type=owner_type, owner_id=owner_id, model=EMBEDDING_MODEL
    )
    if existing is None or existing.content_hash != content_hash(text):
        return None
    return list(existing.embedding)


def upsert_for_candidate(
    session: Session,
    profile: CandidateProfile,
    master: dict[str, Any] | None = None,
    *,
    vector: list[float] | None = None,
) -> EmbeddingResult:
    extras = profile.extras if isinstance(profile.extras, dict) else {}
    payload = master if isinstance(master, dict) else extras.get("master_candidate")
    if not isinstance(payload, dict):
        payload = {}
    return _upsert(
        session,
        owner_type=OWNER_CANDIDATE,
        owner_id=profile.id,
        text=candidate_embedding_text(payload),
        vector=vector,
        assign=lambda row: setattr(profile, "embedding_id", row.id),
    )


def upsert_for_job(
    session: Session,
    job: Job,
    doc: dict[str, Any] | None = None,
    *,
    vector: list[float] | None = None,
) -> EmbeddingResult:
    payload = doc if isinstance(doc, dict) else document_from_job(job)
    return _upsert(
        session,
        owner_type=OWNER_JOB,
        owner_id=job.id,
        text=job_embedding_text(payload),
        vector=vector,
        assign=lambda row: setattr(job, "embedding_id", row.id),
    )


def metadata(row: Embedding, *, cached: bool = False) -> dict[str, Any]:
    return {
        "embedding_id": str(row.id),
        "model": row.model,
        "content_hash": row.content_hash or "",
        "cached": cached,
        "owner_type": row.owner_type,
        "owner_id": str(row.owner_id),
    }


def _upsert(
    session: Session,
    *,
    owner_type: str,
    owner_id: UUID,
    text: str,
    vector: list[float] | None,
    assign,
) -> EmbeddingResult:
    repo = EmbeddingRepository(session)
    existing = repo.get_by_owner(owner_type=owner_type, owner_id=owner_id, model=EMBEDDING_MODEL)
    digest = content_hash(text) if text else ""
    if existing and digest and existing.content_hash == digest:
        assign(existing)
        return EmbeddingResult(row=existing, cached=True)
    if not text:
        return EmbeddingResult(row=existing, skipped=True)
    values = list(vector) if vector else []
    if not values:
        if not is_configured():
            return EmbeddingResult(row=existing, skipped=True)
        try:
            values = embed_text(text)
        except Exception:
            logger.info("embedding_upsert_skipped owner_type=%s", owner_type)
            return EmbeddingResult(row=existing, skipped=True)
    if not values:
        return EmbeddingResult(row=existing, skipped=True)
    row = repo.upsert(
        owner_type=owner_type,
        owner_id=owner_id,
        model=EMBEDDING_MODEL,
        embedding=values,
        content_hash=digest,
    )
    assign(row)
    return EmbeddingResult(row=row, cached=False)


def _section(title: str, values: list[str]) -> str:
    cleaned = [item.strip() for item in values if item and str(item).strip()]
    if not cleaned:
        return ""
    return f"{title}: " + "; ".join(cleaned)


def _dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _named_values(value: Any, key: str) -> list[str]:
    names: list[str] = []
    for item in _dicts(value):
        name = str(item.get(key) or item.get("name") or item.get("skill") or "").strip()
        if name:
            names.append(name)
    if not names and isinstance(value, list):
        names = [str(item).strip() for item in value if not isinstance(item, dict) and str(item).strip()]
    return names


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.replace("\n", ",").split(",") if part.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []
