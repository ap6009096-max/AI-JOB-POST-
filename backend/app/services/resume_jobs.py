from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx

from app.core.config import Environment, settings
from app.db.models import Candidate, User
from app.services.candidates import CandidateService
from app.services.resume_files import EXTENSIONS, ResumeFileError, validate_resume_file
from app.services.resume_parse import (
    DOCX_MIN_CHARS,
    ResumeParseError,
    analyze_resume_text,
    has_parse_evidence,
    normalize_parse_result,
    parse_optional_date,
    parse_resume_bytes,
)
from app.services.resume_storage import get_bytes, put_bytes

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def upload_resume(
    service: CandidateService,
    candidate: Candidate,
    *,
    data: bytes,
    filename: str | None,
    declared_type: str | None,
) -> None:
    content_type = validate_resume_file(data=data, declared_type=declared_type, filename=filename)
    object_key = f"candidates/{candidate.id}/resume/{uuid4()}.{EXTENSIONS[content_type]}"
    put_bytes(object_key, data, content_type)
    started = _now()
    service.update_resume_processing(
        candidate,
        {
            "filename": filename or "resume",
            "content_type": content_type,
            "size_bytes": len(data),
            "object_key": object_key,
            "parse_result": None,
            "processing": {
                "status": "queued",
                "error": "",
                "started_at": started,
                "finished_at": "",
            },
        },
    )
    logger.info("resume_processing_started candidate_id=%s object_key=%s", candidate.id, object_key)
    _enqueue_or_parse(service, candidate, object_key=object_key, content_type=content_type)


def complete_resume_job(
    service: CandidateService,
    candidate: Candidate,
    *,
    status: str,
    text: str = "",
    parse_result: dict | None = None,
    error: str = "",
) -> None:
    current = dict((candidate.profile.extras or {}).get("resume") or {}) if candidate.profile else {}
    processing = dict(current.get("processing") or {})
    processing.update(
        {
            "status": status,
            "error": error if status == "failed" else "",
            "finished_at": _now(),
        }
    )
    payload: dict = {"processing": processing}
    if status == "succeeded":
        payload["text"] = text
        payload["parse_result"] = normalize_parse_result(parse_result)
        logger.info("resume_processing_succeeded candidate_id=%s", candidate.id)
    else:
        logger.info("resume_processing_failed candidate_id=%s", candidate.id)
    service.update_resume_processing(candidate, payload)
    if status == "succeeded":
        _auto_apply_parse(service, candidate, payload.get("parse_result"))


def apply_parse_result(
    service: CandidateService,
    user: User,
    candidate: Candidate,
    approved: dict | None = None,
) -> None:
    resume = dict((candidate.profile.extras or {}).get("resume") or {}) if candidate.profile else {}
    processing = dict(resume.get("processing") or {})
    if processing.get("applied_at"):
        raise ResumeFileError("This extracted profile was already applied. Upload a new resume to review again.")
    stored = resume.get("parse_result")
    if not isinstance(stored, dict):
        raise ResumeFileError("No extracted profile to apply yet")
    parsed = approved if isinstance(approved, dict) else stored
    data = normalize_parse_result(parsed)
    personal = {
        "given_name": data["given_name"],
        "middle_name": data["middle_name"],
        "family_name": data["family_name"],
        "phone": data["phone"],
        "country": data["country"],
        "city": data["city"],
        "address": data["address"],
    }
    personal = {key: value for key, value in personal.items() if value}
    if personal:
        service.update_personal(user, candidate, personal)
    profile_fields = {}
    if data["current_role"]:
        profile_fields["headline"] = data["current_role"]
    if data["summary"]:
        profile_fields["summary"] = data["summary"]
    if profile_fields:
        service.update_profile(candidate, **profile_fields)

    extras = dict((candidate.profile.extras or {}) if candidate.profile else {})
    existing_skills = {row.skill.lower() for row in candidate.skills}
    existing_tech = {
        str(item.get("name") or "").lower()
        for item in extras.get("technologies") or []
        if isinstance(item, dict)
    }
    existing_experience = {(row.title.lower(), row.company_name.lower()) for row in candidate.experience}
    existing_education = {(row.school.lower(), (row.degree or "").lower()) for row in candidate.education}
    existing_projects = {row.name.lower() for row in candidate.projects}
    existing_certifications = {row.name.lower() for row in candidate.certifications}
    existing_achievements = {
        str(item.get("title") or "").lower()
        for item in extras.get("achievements") or []
        if isinstance(item, dict)
    }

    for item in data["experience"]:
        title = str(item.get("title") or "").strip()
        company = str(item.get("company_name") or "").strip()
        key = (title.lower(), company.lower())
        if not title or not company or key in existing_experience:
            continue
        service.create_experience(
            candidate.id,
            company_name=company,
            title=title,
            start_date=parse_optional_date(item.get("start_date")),
            end_date=parse_optional_date(item.get("end_date")),
            description=str(item.get("description") or ""),
        )
        existing_experience.add(key)
    for item in data["education"]:
        school = str(item.get("school") or "").strip()
        degree = str(item.get("degree") or "").strip()
        key = (school.lower(), degree.lower())
        if not school or key in existing_education:
            continue
        service.create_education(
            candidate.id,
            school=school,
            degree=degree,
            field_of_study=str(item.get("field_of_study") or ""),
            start_date=parse_optional_date(item.get("start_date")),
            end_date=parse_optional_date(item.get("end_date")),
        )
        existing_education.add(key)
    for item in data["skills"]:
        skill = str(item.get("skill") or "").strip()
        if not skill or skill.lower() in existing_skills:
            continue
        years = _as_years(item.get("years"))
        service.create_skill(candidate.id, skill=skill, years=years)
        existing_skills.add(skill.lower())
    for item in data["technologies"]:
        name = str(item.get("name") or "").strip()
        if not name or name.lower() in existing_tech:
            continue
        years = _as_years(item.get("years"))
        service.create_technology(candidate, name=name, years=years)
        existing_tech.add(name.lower())
    for item in data["projects"]:
        name = str(item.get("name") or "").strip()
        if not name or name.lower() in existing_projects:
            continue
        service.create_project(
            candidate.id,
            name=name,
            description=str(item.get("description") or ""),
            url=str(item.get("url") or "") or None,
        )
        existing_projects.add(name.lower())
    for item in data["certifications"]:
        name = str(item.get("name") or "").strip()
        if not name or name.lower() in existing_certifications:
            continue
        service.create_certification(
            candidate.id,
            name=name,
            issuer=str(item.get("issuer") or ""),
            issued_on=parse_optional_date(item.get("issued_on")),
        )
        existing_certifications.add(name.lower())
    for item in data["achievements"]:
        title = str(item.get("title") or "").strip()
        if not title or title.lower() in existing_achievements:
            continue
        service.create_achievement(
            candidate,
            title=title,
            description=str(item.get("description") or ""),
            occurred_on=parse_optional_date(item.get("occurred_on")),
        )
        existing_achievements.add(title.lower())

    processing["applied_at"] = _now()
    service.update_resume_processing(
        candidate,
        {"processing": processing, "parse_result": data},
    )


def parse_pasted_resume(service: CandidateService, candidate: Candidate, text: str) -> None:
    stripped = text.strip()
    if len(stripped) < DOCX_MIN_CHARS:
        return
    try:
        parsed = analyze_resume_text(stripped)
    except ResumeParseError:
        logger.info("resume_paste_analyze_failed candidate_id=%s", candidate.id)
        return
    if not has_parse_evidence(parsed):
        return
    current = dict((candidate.profile.extras or {}).get("resume") or {}) if candidate.profile else {}
    processing = dict(current.get("processing") or {})
    processing.pop("applied_at", None)
    processing.update({"status": "processing", "error": "", "started_at": processing.get("started_at") or _now()})
    service.update_resume_processing(candidate, {"processing": processing})
    complete_resume_job(service, candidate, status="succeeded", text=stripped, parse_result=parsed)


def _auto_apply_parse(service: CandidateService, candidate: Candidate, parsed: dict | None) -> None:
    if not has_parse_evidence(parsed):
        return
    user = candidate.user
    if user is None and candidate.user_id is not None:
        user = service.session.get(User, candidate.user_id)
    if user is None:
        logger.info("resume_auto_apply_skipped_no_user candidate_id=%s", candidate.id)
        return
    try:
        apply_parse_result(service, user, candidate)
    except ResumeFileError:
        logger.info("resume_auto_apply_skipped candidate_id=%s", candidate.id)


def _enqueue_or_parse(
    service: CandidateService,
    candidate: Candidate,
    *,
    object_key: str,
    content_type: str,
) -> None:
    queued = _enqueue_worker(candidate.id, object_key=object_key, content_type=content_type)
    if queued:
        return
    if settings.environment is not Environment.LOCAL:
        complete_resume_job(
            service,
            candidate,
            status="failed",
            error="Resume processing is temporarily unavailable",
        )
        return
    _parse_inline(service, candidate, object_key=object_key, content_type=content_type)


def _enqueue_worker(candidate_id: UUID, *, object_key: str, content_type: str) -> bool:
    from app.services.cloud_tasks import enqueue_parse_resume

    if enqueue_parse_resume(candidate_id, object_key=object_key, content_type=content_type):
        return True
    if settings.use_cloud_tasks:
        logger.info("resume_cloud_tasks_enqueue_failed candidate_id=%s", candidate_id)
        return False
    if not settings.worker_url:
        return False
    headers = {"Content-Type": "application/json"}
    secret = settings.worker_shared_secret
    if secret is not None:
        headers["X-Worker-Secret"] = secret.get_secret_value()
    try:
        response = httpx.post(
            f"{settings.worker_url.rstrip('/')}/tasks",
            headers=headers,
            json={
                "task_type": "parse_resume",
                "reference_id": str(candidate_id),
                "payload": {
                    "candidate_id": str(candidate_id),
                    "object_key": object_key,
                    "content_type": content_type,
                },
            },
            timeout=2.0,
        )
        response.raise_for_status()
        return True
    except Exception:
        logger.info("resume_worker_enqueue_failed candidate_id=%s", candidate_id)
        return False


def _parse_inline(
    service: CandidateService,
    candidate: Candidate,
    *,
    object_key: str,
    content_type: str,
) -> None:
    current = dict((candidate.profile.extras or {}).get("resume") or {}) if candidate.profile else {}
    processing = dict(current.get("processing") or {})
    processing.update({"status": "processing", "error": ""})
    service.update_resume_processing(candidate, {"processing": processing})
    try:
        data = get_bytes(object_key)
        text, parsed = parse_resume_bytes(data, content_type)
        complete_resume_job(service, candidate, status="succeeded", text=text, parse_result=parsed)
    except ResumeParseError as exc:
        logger.info("resume_%s_failed candidate_id=%s", exc.stage, candidate.id)
        complete_resume_job(service, candidate, status="failed", error=str(exc))
    except Exception:
        logger.exception("resume_processing_failed candidate_id=%s", candidate.id)
        complete_resume_job(
            service,
            candidate,
            status="failed",
            error="Could not process this resume. Try another file.",
        )


def _as_years(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
