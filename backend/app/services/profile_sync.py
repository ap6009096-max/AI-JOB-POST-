from __future__ import annotations

import hashlib
import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import Candidate, CandidateProfile, CandidateSource
from app.db.repositories import ProfileVersionRepository
from app.schemas.candidate import MasterCandidate
from app.schemas.source import SourceAgentResult, utc_now
from app.services.audit import AuditService
from app.services.embedding_service import upsert_for_candidate

logger = logging.getLogger(__name__)

IDENTITY_FIELDS = (
    "given_name",
    "middle_name",
    "family_name",
    "current_role",
    "summary",
    "city",
    "country",
)


def fingerprint_evidence(result: SourceAgentResult) -> str:
    evidence = result.evidence if isinstance(result.evidence, dict) else {}
    repos = evidence.get("repositories") if isinstance(evidence.get("repositories"), list) else []
    languages = evidence.get("languages") if isinstance(evidence.get("languages"), list) else []
    payload = {
        "url": result.url or "",
        "login": evidence.get("login") or "",
        "languages": sorted(str(item) for item in languages),
        "repos": sorted(
            str(item.get("name") or "") for item in repos if isinstance(item, dict)
        ),
        "excerpt": str(evidence.get("text_excerpt") or "")[:2000],
    }
    encoded = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def merge_master(current: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    base = MasterCandidate.model_validate(current or {}).model_dump()
    proposed = MasterCandidate.model_validate(incoming or {}).model_dump()
    merged = dict(base)
    for field in IDENTITY_FIELDS:
        existing = str(base.get(field) or "").strip()
        merged[field] = existing or str(proposed.get(field) or "").strip()
    merged["skills"] = _union_named(base.get("skills"), proposed.get("skills"), "skill")
    merged["technologies"] = _union_named(base.get("technologies"), proposed.get("technologies"), "name")
    merged["experience"] = _union_experience(base.get("experience"), proposed.get("experience"))
    merged["education"] = _union_named(base.get("education"), proposed.get("education"), "school")
    merged["projects"] = _union_named(base.get("projects"), proposed.get("projects"), "name")
    merged["certifications"] = _union_named(base.get("certifications"), proposed.get("certifications"), "name")
    merged["achievements"] = _union_named(base.get("achievements"), proposed.get("achievements"), "title")
    merged["sources"] = _union_sources(base.get("sources"), proposed.get("sources"))
    merged["provenance"] = _merge_provenance(base.get("provenance"), proposed.get("provenance"))
    merged["timestamp"] = utc_now()
    return MasterCandidate.model_validate(merged).model_dump()


def diff_master(current: dict[str, Any], merged: dict[str, Any]) -> dict[str, Any]:
    added: dict[str, list[str]] = {}
    for field, key in (
        ("skills", "skill"),
        ("technologies", "name"),
        ("projects", "name"),
        ("experience", "title"),
    ):
        before = _name_set(current.get(field), key if field != "experience" else None)
        after = _name_set(merged.get(field), key if field != "experience" else None)
        extra = sorted(after - before)
        if extra:
            added[field] = extra
    identity_filled = [
        field
        for field in ("summary", "current_role")
        if not str((current or {}).get(field) or "").strip() and str((merged or {}).get(field) or "").strip()
    ]
    if identity_filled:
        added["identity"] = identity_filled
    material = bool(added)
    return {"added": added, "unchanged": not material, "material": material}


def apply_source_update(
    session: Session,
    candidate: Candidate,
    user_id: UUID | None,
    source_row: CandidateSource,
    result: SourceAgentResult,
) -> dict[str, Any]:
    extras = dict(source_row.extras or {})
    previous = str(extras.get("content_fingerprint") or "")
    extras.update(result.to_extras())
    digest = fingerprint_evidence(result)
    extras["content_fingerprint"] = digest
    source_row.extras = extras
    flag_modified(source_row, "extras")
    if result.fetch_status != "ok":
        return {"applied": False, "reason": result.fetch_status or "source_failure"}
    if previous and digest == previous:
        return {"applied": False, "reason": "unchanged"}
    incoming = master_from_source(source_row.source, result)
    return apply_master_proposal(
        session,
        candidate,
        user_id,
        incoming,
        source=source_row.source or "source",
        fingerprint=digest,
    )


def apply_master_proposal(
    session: Session,
    candidate: Candidate,
    user_id: UUID | None,
    proposed_master: dict[str, Any],
    *,
    source: str = "pipeline",
    fingerprint: str = "",
    embedding: list[float] | None = None,
) -> dict[str, Any]:
    profile = candidate.profile
    if profile is None:
        return {"applied": False, "reason": "missing_profile"}
    extras = dict(profile.extras or {})
    current = extras.get("master_candidate") if isinstance(extras.get("master_candidate"), dict) else {}
    merged = merge_master(current, proposed_master)
    change = diff_master(current, merged)
    change["source"] = source
    change["fingerprint"] = fingerprint
    if current and not change["material"]:
        extras["master_candidate"] = current
        profile.extras = extras
        flag_modified(profile, "extras")
        return {"applied": False, "reason": "unchanged", "change_summary": change}
    versions = ProfileVersionRepository(session)
    version = versions.next_version(candidate.id)
    versions.create(
        candidate_id=candidate.id,
        version=version,
        snapshot=merged,
        change_summary=change,
        source=source,
    )
    extras["master_candidate"] = merged
    profile.extras = extras
    flag_modified(profile, "extras")
    embedded = False
    if change["material"]:
        embedded = _upsert_embedding(session, profile, merged, embedding)
    AuditService(session).create(
        action="candidate_master_updated" if source == "pipeline" else "candidate_profile_source_updated",
        entity_type="candidate_profile",
        actor_user_id=user_id,
        entity_id=profile.id,
        metadata={"source": source, "version": version, "change_summary": change, "embedded": embedded},
    )
    return {
        "applied": True,
        "version": version,
        "change_summary": change,
        "embedded": embedded,
        "master": merged,
    }


def master_from_source(source: str, result: SourceAgentResult) -> dict[str, Any]:
    analysis = result.analysis if isinstance(result.analysis, dict) else {}
    evidence = result.evidence if isinstance(result.evidence, dict) else {}
    skills = _skill_items(analysis.get("skills"))
    technologies = _tech_items(analysis.get("technologies") or evidence.get("languages") or analysis.get("skills"))
    projects = _project_items(analysis.get("projects")) or _repo_projects(evidence.get("repositories"))
    return MasterCandidate(
        current_role=str(analysis.get("title") or ""),
        summary=str(analysis.get("summary") or ""),
        skills=skills,
        technologies=technologies,
        projects=projects,
        sources=[
            {
                "source": source,
                "url": result.url,
                "fetch_status": result.fetch_status,
                "skip_reason": result.skip_reason,
                "evidence": evidence,
                "analysis": analysis,
                "provenance": result.provenance,
            }
        ],
        provenance={
            "skills": [source] if skills else [],
            "technologies": [source] if technologies else [],
            "projects": [source] if projects else [],
        },
        timestamp=utc_now(),
    ).model_dump()


def _upsert_embedding(
    session: Session,
    profile: CandidateProfile,
    master: dict[str, Any],
    embedding: list[float] | None,
) -> bool:
    result = upsert_for_candidate(session, profile, master, vector=embedding)
    return result.row is not None and not result.skipped


def _skill_items(value: object) -> list[dict[str, Any]]:
    return _named_items(value, "skill")


def _tech_items(value: object) -> list[dict[str, Any]]:
    return _named_items(value, "name")


def _project_items(value: object) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return items
    for raw in value:
        if isinstance(raw, dict):
            name = str(raw.get("name") or "").strip()
            if name:
                items.append(
                    {
                        "name": name,
                        "description": str(raw.get("description") or ""),
                        "url": str(raw.get("url") or ""),
                    }
                )
        elif isinstance(raw, str) and raw.strip():
            items.append({"name": raw.strip(), "description": "", "url": ""})
    return items


def _repo_projects(value: object) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return items
    for raw in value:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if name:
            items.append(
                {
                    "name": name,
                    "description": str(raw.get("description") or ""),
                    "url": str(raw.get("url") or raw.get("html_url") or ""),
                }
            )
    return items


def _named_items(value: object, key: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return items
    for raw in value:
        if isinstance(raw, dict):
            name = str(raw.get(key) or raw.get("name") or raw.get("skill") or "").strip()
            if name:
                item = {key: name}
                if "years" in raw:
                    item["years"] = raw.get("years")
                items.append(item)
        elif isinstance(raw, str) and raw.strip():
            items.append({key: raw.strip()})
    return items


def _union_named(existing: object, incoming: object, key: str) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in _named_items(existing, key) + _named_items(incoming, key):
        name = str(item.get(key) or "").strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        merged.append(item)
    return merged


def _union_experience(existing: object, incoming: object) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    rows: list[dict[str, Any]] = []
    for value in (existing, incoming):
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, dict))
    for item in rows:
        key = (
            str(item.get("title") or "").strip().lower(),
            str(item.get("company_name") or "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _union_sources(existing: object, incoming: object) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    rows: list[dict[str, Any]] = []
    for value in (existing, incoming):
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, dict))
    for item in rows:
        key = (str(item.get("source") or "").strip().lower(), str(item.get("url") or "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _merge_provenance(existing: object, incoming: object) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for blob in (existing, incoming):
        if not isinstance(blob, dict):
            continue
        for key, values in blob.items():
            names = merged.setdefault(str(key), [])
            if not isinstance(values, list):
                continue
            for value in values:
                text = str(value).strip()
                if text and text not in names:
                    names.append(text)
    return merged


def _name_set(value: object, key: str | None) -> set[str]:
    names: set[str] = set()
    if not isinstance(value, list):
        return names
    for item in value:
        if not isinstance(item, dict):
            continue
        if key:
            name = str(item.get(key) or "").strip().lower()
        else:
            name = f"{item.get('title') or ''}|{item.get('company_name') or ''}".strip().lower()
        if name:
            names.add(name)
    return names
