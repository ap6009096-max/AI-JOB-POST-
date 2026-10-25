from __future__ import annotations

import logging
import re
from typing import Any

from langgraph.config import get_config
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import Job
from app.graphs.job_state import JobGraphState
from app.schemas.source import utc_now
from app.services.embedding_service import upsert_for_job
from app.services.gemini_service import GeminiError, is_configured, review_job
from app.services.job_document import (
    JOB_JSON_KEY,
    PIPELINE_KEY,
    document_from_fields,
    document_from_job,
    fields_from_payload,
    persist_blob,
    validate_for_publish,
)

logger = logging.getLogger(__name__)

CHECK_COMPLETE = "complete"
CHECK_MISSING = "missing"
CHECK_AMBIGUOUS = "ambiguous"
CHECK_INVALID = "invalid"

REQUIRED_FIELDS = ("title", "description", "location", "required_skills", "employment_type")
GENERIC_SKILLS = {
    "coding",
    "communication",
    "teamwork",
    "hardworking",
    "smart",
    "skills",
    "ms office",
    "computer",
    "software",
    "programming",
}
VAGUE_EDUCATION = re.compile(
    r"^(any\s+)?(degree|graduation|graduate|educated)s?(\s+preferred)?$",
    re.IGNORECASE,
)
AMBIGUOUS_SALARY = {
    "negotiable",
    "competitive",
    "doe",
    "depends",
    "tbd",
    "n/a",
    "na",
    "salary negotiable",
    "compensation competitive",
    "competitive salary",
}
_AMOUNT = re.compile(r"(?<![A-Za-z])(\d+(?:,\d{3})*(?:\.\d+)?)\s*([kK])?")
MIN_DESCRIPTION_LENGTH = 80


def load_job(state: JobGraphState) -> dict[str, Any]:
    job = _job()
    doc = document_from_job(job)
    fields = fields_from_payload(doc)
    return {
        "job_id": str(job.id),
        "fields": fields,
        "status": "running",
        **_done("load_job"),
    }


def required_field_check(state: JobGraphState) -> dict[str, Any]:
    fields = _fields(state)
    checks = [
        _check(name, CHECK_COMPLETE if _present(fields, name) else CHECK_MISSING, "" if _present(fields, name) else f"{name} is required")
        for name in REQUIRED_FIELDS
    ]
    return {"checks": checks, **_done("required_field_check")}


def description_quality_check(state: JobGraphState) -> dict[str, Any]:
    fields = _fields(state)
    description = str(fields.get("description") or "").strip()
    title = str(fields.get("title") or "").strip()
    if not description:
        return {
            "checks": [_check("description", CHECK_MISSING, "Job description is empty")],
            **_done("description_quality_check"),
        }
    lowered = description.casefold()
    title_cf = title.casefold()
    repeats_title = bool(title_cf) and (lowered == title_cf or lowered.startswith(title_cf) and len(description) < MIN_DESCRIPTION_LENGTH)
    if len(description) < MIN_DESCRIPTION_LENGTH or repeats_title:
        return {
            "checks": [
                _check(
                    "description",
                    CHECK_AMBIGUOUS,
                    "Description is too short or mostly repeats the title",
                )
            ],
            **_done("description_quality_check"),
        }
    return {"checks": [_check("description", CHECK_COMPLETE)], **_done("description_quality_check")}


def skill_check(state: JobGraphState) -> dict[str, Any]:
    skills = _string_list(_fields(state).get("required_skills"))
    if not skills:
        return {
            "checks": [_check("required_skills", CHECK_MISSING, "At least one required skill is needed")],
            **_done("skill_check"),
        }
    if all(skill.casefold() in GENERIC_SKILLS for skill in skills):
        return {
            "checks": [_check("required_skills", CHECK_AMBIGUOUS, "Required skills are too generic")],
            **_done("skill_check"),
        }
    return {"checks": [_check("required_skills", CHECK_COMPLETE)], **_done("skill_check")}


def experience_check(state: JobGraphState) -> dict[str, Any]:
    experience = _fields(state).get("experience")
    years = 0.0
    text = ""
    if isinstance(experience, dict):
        try:
            years = float(experience.get("years") or 0)
        except (TypeError, ValueError):
            years = 0.0
        text = str(experience.get("text") or "").strip()
    if years < 0:
        return {
            "checks": [_check("experience", CHECK_INVALID, "Experience years cannot be negative")],
            **_done("experience_check"),
        }
    if years == 0 and not text:
        return {
            "checks": [_check("experience", CHECK_MISSING, "Experience is not specified")],
            **_done("experience_check"),
        }
    if years == 0 and text:
        return {
            "checks": [_check("experience", CHECK_AMBIGUOUS, "Experience text is present without years")],
            **_done("experience_check"),
        }
    return {"checks": [_check("experience", CHECK_COMPLETE)], **_done("experience_check")}


def education_check(state: JobGraphState) -> dict[str, Any]:
    education = str(_fields(state).get("education") or "").strip()
    if not education:
        return {
            "checks": [_check("education", CHECK_MISSING, "Education is not specified")],
            **_done("education_check"),
        }
    if VAGUE_EDUCATION.match(education):
        return {
            "checks": [_check("education", CHECK_AMBIGUOUS, "Education is too vague")],
            **_done("education_check"),
        }
    return {"checks": [_check("education", CHECK_COMPLETE)], **_done("education_check")}


def technology_check(state: JobGraphState) -> dict[str, Any]:
    fields = _fields(state)
    technologies = _string_list(fields.get("technologies"))
    if not technologies:
        return {
            "checks": [_check("technologies", CHECK_MISSING, "No technologies listed")],
            **_done("technology_check"),
        }
    skill_keys = {item.casefold() for item in _string_list(fields.get("required_skills"))}
    skill_keys.update(item.casefold() for item in _string_list(fields.get("preferred_skills")))
    tech_keys = {item.casefold() for item in technologies}
    if skill_keys and tech_keys <= skill_keys:
        return {
            "checks": [_check("technologies", CHECK_AMBIGUOUS, "Technologies only repeat listed skills")],
            **_done("technology_check"),
        }
    return {"checks": [_check("technologies", CHECK_COMPLETE)], **_done("technology_check")}


def salary_check(state: JobGraphState) -> dict[str, Any]:
    text = str(_fields(state).get("salary_range") or "").strip()
    if not text:
        return {
            "checks": [_check("salary_range", CHECK_MISSING, "Salary range is not specified")],
            **_done("salary_check"),
        }
    lowered = text.casefold()
    if lowered in AMBIGUOUS_SALARY:
        return {
            "checks": [_check("salary_range", CHECK_AMBIGUOUS, "Salary is too vague")],
            **_done("salary_check"),
        }
    normalized = text.replace("–", "-").replace("—", "-").strip()
    if normalized.startswith("-") and not re.search(r"\d\s*-\s*\d", normalized):
        return {
            "checks": [_check("salary_range", CHECK_INVALID, "Salary cannot be negative")],
            **_done("salary_check"),
        }
    amounts = _salary_amounts(text)
    if len(amounts) >= 2 and amounts[0] > amounts[-1]:
        return {
            "checks": [_check("salary_range", CHECK_INVALID, "Salary maximum is below the minimum")],
            **_done("salary_check"),
        }
    if not amounts:
        return {
            "checks": [_check("salary_range", CHECK_AMBIGUOUS, "Salary range could not be parsed")],
            **_done("salary_check"),
        }
    return {"checks": [_check("salary_range", CHECK_COMPLETE)], **_done("salary_check")}


def duplicate_check(state: JobGraphState) -> dict[str, Any]:
    job = _job()
    session = _session()
    title = str(_fields(state).get("title") or "").strip()
    title_cf = title.casefold()
    if not title_cf:
        return {
            "checks": [_check("title", CHECK_MISSING, "Title is required")],
            **_done("duplicate_check"),
        }
    others = list(
        session.scalars(select(Job).where(Job.company_id == job.company_id, Job.id != job.id))
    )
    exact = False
    similar = False
    for other in others:
        other_title = (other.title or "").strip().casefold()
        if not other_title or not title_cf:
            continue
        if other_title == title_cf:
            exact = True
            break
        if len(title_cf) >= 8 and len(other_title) >= 8 and (title_cf in other_title or other_title in title_cf):
            similar = True
    if exact:
        return {
            "checks": [_check("title", CHECK_INVALID, "Another job at this company has the same title")],
            **_done("duplicate_check"),
        }
    if similar:
        return {
            "checks": [_check("title", CHECK_AMBIGUOUS, "Another job at this company has a similar title")],
            **_done("duplicate_check"),
        }
    return {"checks": [_check("title", CHECK_COMPLETE, "Title is unique at this company")], **_done("duplicate_check")}


def gemini_review(state: JobGraphState) -> dict[str, Any]:
    if not is_configured():
        return {
            "skipped": [_skip("Gemini_review", "ai_failure")],
            **_done("Gemini_review"),
        }
    fields = _fields(state)
    payload = {
        "title": fields.get("title") or "",
        "description": fields.get("description") or "",
        "location": fields.get("location") or "",
        "required_skills": fields.get("required_skills") or [],
        "preferred_skills": fields.get("preferred_skills") or [],
        "experience": fields.get("experience") or {},
        "education": fields.get("education") or "",
        "technologies": fields.get("technologies") or [],
        "salary_range": fields.get("salary_range") or "",
        "employment_type": fields.get("employment_type") or "",
    }
    try:
        review = review_job(payload)
    except GeminiError as exc:
        logger.info("job_pipeline_gemini_failed error=%s", exc)
        return {
            "errors": [_error("Gemini_review", "ai_failure", str(exc))],
            "skipped": [_skip("Gemini_review", "ai_failure")],
            **_done("Gemini_review"),
        }
    allowed = {CHECK_COMPLETE, CHECK_MISSING, CHECK_AMBIGUOUS, CHECK_INVALID}
    checks = []
    for note in review.notes:
        status = str(note.status or "").strip().lower()
        if status not in allowed:
            continue
        field = str(note.field or "review").strip() or "review"
        checks.append(_check(field, status, str(note.message or "")))
    return {"review": review.overall, "checks": checks, **_done("Gemini_review")}


def normalize_job(state: JobGraphState) -> dict[str, Any]:
    fields = fields_from_payload(_fields(state), existing=_fields(state))
    return {"fields": fields, "normalized": fields, **_done("normalize_job")}


def validate_job(state: JobGraphState) -> dict[str, Any]:
    job = _job()
    normalized = state.get("normalized") if isinstance(state.get("normalized"), dict) else _fields(state)
    doc = document_from_fields(
        normalized,
        status=job.status,
        job_id=str(job.id),
        company_id=str(job.company_id),
        title_fallback=job.title,
        description_fallback=job.description,
        location_fallback=job.location,
    )
    publish_errors = validate_for_publish(doc)
    checks = list(state.get("checks") or [])
    has_invalid = any(item.get("status") == CHECK_INVALID for item in checks)
    required_missing = any(
        item.get("field") in REQUIRED_FIELDS and item.get("status") == CHECK_MISSING for item in checks
    )
    validation_ok = not publish_errors and not has_invalid and not required_missing
    errors = [_error("validate_job", "validation_failure", message) for message in publish_errors]
    update: dict[str, Any] = {"job_json": doc, "validation_ok": validation_ok, **_done("validate_job")}
    if errors:
        update["errors"] = errors
    return update


def create_job_json(state: JobGraphState) -> dict[str, Any]:
    job = _job()
    normalized = state.get("normalized") if isinstance(state.get("normalized"), dict) else _fields(state)
    doc = state.get("job_json") if isinstance(state.get("job_json"), dict) else document_from_fields(
        normalized,
        status=job.status,
        job_id=str(job.id),
        company_id=str(job.company_id),
        title_fallback=job.title,
        description_fallback=job.description,
        location_fallback=job.location,
    )
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
        "current_node": "create_job_json",
        "steps": list(state.get("steps") or []) + [_step("create_job_json", "done")],
        "errors": errors,
        "skipped": skipped,
        "checks": list(state.get("checks") or []),
        "updated_at": utc_now(),
        "review": str(state.get("review") or ""),
    }
    blob = persist_blob(normalized, extras={PIPELINE_KEY: pipeline, JOB_JSON_KEY: doc})
    job.requirements = blob
    flag_modified(job, "requirements")
    upsert_for_job(_session(), job, doc)
    return {
        "job_json": doc,
        "status": status,
        "current_node": "create_job_json",
        "steps": [_step("create_job_json", "done")],
    }


def _job() -> Job:
    job = (get_config().get("configurable") or {}).get("job")
    if job is None:
        raise RuntimeError("job graph requires a job")
    return job


def _session():
    session = (get_config().get("configurable") or {}).get("session")
    if session is None:
        raise RuntimeError("job graph requires a database session")
    return session


def _fields(state: JobGraphState) -> dict[str, Any]:
    fields = state.get("fields")
    return fields if isinstance(fields, dict) else {}


def _present(fields: dict[str, Any], name: str) -> bool:
    value = fields.get(name)
    if name == "required_skills":
        return bool(_string_list(value))
    return bool(str(value or "").strip())


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _salary_amounts(text: str) -> list[float]:
    values: list[float] = []
    for match in _AMOUNT.finditer(text.replace("–", "-").replace("—", "-")):
        raw = match.group(1).replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        if match.group(2):
            value *= 1000
        values.append(value)
    return values


def _check(field: str, status: str, message: str = "") -> dict[str, str]:
    return {"field": field, "status": status, "message": message}


def _done(node: str) -> dict[str, Any]:
    return {"current_node": node, "steps": [_step(node, "done")]}


def _step(node: str, status: str) -> dict[str, str]:
    return {"node": node, "status": status, "at": utc_now()}


def _skip(node: str, reason: str) -> dict[str, str]:
    return {"node": node, "reason": reason}


def _error(node: str, code: str, message: str) -> dict[str, str]:
    return {"node": node, "code": code, "message": message}
