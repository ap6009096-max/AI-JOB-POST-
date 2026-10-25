from __future__ import annotations

from typing import Any

from app.db.models import Job


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.replace("\n", ",").split(",")
        return [part.strip() for part in parts if part.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in values:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered


def _experience(value: Any, years_fallback: Any = 0) -> dict[str, Any]:
    years = 0.0
    text = ""
    if isinstance(value, dict):
        years = float(value.get("years") or 0)
        text = str(value.get("text") or "")
    elif value not in (None, ""):
        text = str(value)
    if not years:
        try:
            years = float(years_fallback or 0)
        except (TypeError, ValueError):
            years = 0.0
    return {"years": years, "text": text}


def derive_keywords(*, title: str, technologies: list[str], seniority: str, extra: list[str]) -> list[str]:
    tokens: list[str] = []
    for part in title.replace("/", " ").replace("-", " ").split():
        cleaned = part.strip(".,").strip()
        if len(cleaned) > 2:
            tokens.append(cleaned)
    tokens.extend(technologies)
    if seniority:
        tokens.append(seniority)
    tokens.extend(extra)
    return _unique(tokens)


def canonical_fields(
    *,
    title: str = "",
    description: str = "",
    location: str = "",
    required_skills: list[str] | None = None,
    preferred_skills: list[str] | None = None,
    experience: dict[str, Any] | None = None,
    education: str = "",
    technologies: list[str] | None = None,
    responsibilities: list[str] | None = None,
    salary_range: str = "",
    employment_type: str = "",
    seniority: str = "",
    certifications: list[str] | None = None,
    openings: int = 1,
    deadline: str = "",
    extra_keywords: list[str] | None = None,
) -> dict[str, Any]:
    required = _unique(_string_list(required_skills))
    preferred = _unique(_string_list(preferred_skills))
    tech = _unique(_string_list(technologies))
    exp = _experience(experience)
    loc = location.strip()
    keywords = derive_keywords(
        title=title,
        technologies=tech,
        seniority=seniority.strip(),
        extra=_string_list(extra_keywords),
    )
    try:
        openings_n = max(1, int(openings or 1))
    except (TypeError, ValueError):
        openings_n = 1
    return {
        "title": title.strip(),
        "description": description.strip() if isinstance(description, str) else str(description or ""),
        "location": loc,
        "required_skills": required,
        "preferred_skills": preferred,
        "experience": exp,
        "education": education.strip() if isinstance(education, str) else str(education or ""),
        "technologies": tech,
        "responsibilities": _unique(_string_list(responsibilities)),
        "salary_range": salary_range.strip() if isinstance(salary_range, str) else str(salary_range or ""),
        "employment_type": employment_type.strip() if isinstance(employment_type, str) else str(employment_type or ""),
        "seniority": seniority.strip() if isinstance(seniority, str) else str(seniority or ""),
        "certifications": _unique(_string_list(certifications)),
        "openings": openings_n,
        "deadline": deadline.strip() if isinstance(deadline, str) else str(deadline or ""),
        "requirements": {
            "skills": required,
            "experience_years": exp["years"],
            "location": loc,
            "keywords": keywords,
            "required_skills": required,
            "preferred_skills": preferred,
            "experience": exp,
            "education": education.strip() if isinstance(education, str) else str(education or ""),
            "technologies": tech,
            "responsibilities": _unique(_string_list(responsibilities)),
            "salary_range": salary_range.strip() if isinstance(salary_range, str) else str(salary_range or ""),
            "employment_type": employment_type.strip() if isinstance(employment_type, str) else str(employment_type or ""),
            "seniority": seniority.strip() if isinstance(seniority, str) else str(seniority or ""),
            "certifications": _unique(_string_list(certifications)),
            "openings": openings_n,
            "deadline": deadline.strip() if isinstance(deadline, str) else str(deadline or ""),
        },
    }


def fields_from_payload(payload: dict[str, Any], *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    current = dict(existing or {})
    req = payload.get("requirements") if isinstance(payload.get("requirements"), dict) else {}
    current_req = current.get("requirements") if isinstance(current.get("requirements"), dict) else current

    def pick_list(*keys: str) -> list[str] | None:
        for key in keys:
            if key in payload and payload[key] is not None:
                return _string_list(payload[key])
            if key in req and req[key] is not None:
                return _string_list(req[key])
        return None

    def pick_str(*keys: str) -> str | None:
        for key in keys:
            if key in payload and payload[key] is not None:
                return str(payload[key])
            if key in req and req[key] is not None:
                return str(req[key])
        return None

    required = pick_list("required_skills", "skills")
    if required is None:
        required = _string_list(current.get("required_skills") or current_req.get("skills"))

    experience_in = payload.get("experience")
    if experience_in is None:
        experience_in = req.get("experience")
    years_fallback = req.get("experience_years")
    if years_fallback is None:
        years_fallback = current_req.get("experience_years") or (current.get("experience") or {}).get("years")
    if experience_in is None and "experience" not in payload:
        experience_in = current.get("experience") or current_req.get("experience")

    location = pick_str("location")
    if location is None:
        location = str(current.get("location") or current_req.get("location") or "")

    title = pick_str("title")
    if title is None:
        title = str(current.get("title") or "")

    description = pick_str("description")
    if description is None:
        description = str(current.get("description") or "")

    openings = payload.get("openings")
    if openings is None:
        openings = req.get("openings")
    if openings is None:
        openings = current.get("openings") or current_req.get("openings") or 1

    extra_keywords = pick_list("keywords")
    if extra_keywords is None:
        extra_keywords = _string_list(current_req.get("keywords"))

    return canonical_fields(
        title=title,
        description=description,
        location=location,
        required_skills=required,
        preferred_skills=pick_list("preferred_skills")
        if pick_list("preferred_skills") is not None
        else _string_list(current.get("preferred_skills") or current_req.get("preferred_skills")),
        experience=_experience(experience_in, years_fallback),
        education=pick_str("education")
        if pick_str("education") is not None
        else str(current.get("education") or current_req.get("education") or ""),
        technologies=pick_list("technologies")
        if pick_list("technologies") is not None
        else _string_list(current.get("technologies") or current_req.get("technologies")),
        responsibilities=pick_list("responsibilities")
        if pick_list("responsibilities") is not None
        else _string_list(current.get("responsibilities") or current_req.get("responsibilities")),
        salary_range=pick_str("salary_range")
        if pick_str("salary_range") is not None
        else str(current.get("salary_range") or current_req.get("salary_range") or ""),
        employment_type=pick_str("employment_type")
        if pick_str("employment_type") is not None
        else str(current.get("employment_type") or current_req.get("employment_type") or ""),
        seniority=pick_str("seniority")
        if pick_str("seniority") is not None
        else str(current.get("seniority") or current_req.get("seniority") or ""),
        certifications=pick_list("certifications")
        if pick_list("certifications") is not None
        else _string_list(current.get("certifications") or current_req.get("certifications")),
        openings=int(openings or 1),
        deadline=pick_str("deadline")
        if pick_str("deadline") is not None
        else str(current.get("deadline") or current_req.get("deadline") or ""),
        extra_keywords=extra_keywords,
    )


def document_from_job(job: Job) -> dict[str, Any]:
    extras = job.requirements if isinstance(job.requirements, dict) else {}
    fields = fields_from_payload(
        {
            "title": job.title,
            "description": job.description,
            "location": job.location,
            "requirements": extras,
        },
        existing={"title": job.title, "description": job.description, "location": job.location, **extras},
    )
    return document_from_fields(
        fields,
        status=job.status,
        job_id=str(job.id),
        company_id=str(job.company_id),
        title_fallback=job.title,
        description_fallback=job.description,
        location_fallback=job.location,
    )


def document_from_fields(
    fields: dict[str, Any],
    *,
    status: str = "draft",
    job_id: str = "",
    company_id: str = "",
    title_fallback: str = "",
    description_fallback: str = "",
    location_fallback: str = "",
) -> dict[str, Any]:
    ranking = fields["requirements"]
    return {
        "id": job_id,
        "company_id": company_id,
        "status": status,
        "title": fields["title"] or title_fallback,
        "description": fields["description"] if fields["description"] else description_fallback,
        "location": fields["location"] or location_fallback,
        "required_skills": fields["required_skills"],
        "preferred_skills": fields["preferred_skills"],
        "experience": fields["experience"],
        "education": fields["education"],
        "technologies": fields["technologies"],
        "responsibilities": fields["responsibilities"],
        "salary_range": fields["salary_range"],
        "employment_type": fields["employment_type"],
        "seniority": fields["seniority"],
        "certifications": fields["certifications"],
        "openings": fields["openings"],
        "deadline": fields["deadline"],
        "requirements": {
            "skills": ranking["skills"],
            "experience_years": ranking["experience_years"],
            "location": ranking["location"],
            "keywords": ranking["keywords"],
        },
    }


def ranking_dict(job: Job) -> dict[str, Any]:
    doc = document_from_job(job)
    return {
        "id": doc["id"],
        "company_id": doc["company_id"],
        "title": doc["title"],
        "description": doc["description"],
        "location": doc["location"],
        "status": doc["status"],
        "requirements": doc["requirements"],
    }


PIPELINE_KEY = "job_pipeline"
JOB_JSON_KEY = "job_json"
RESERVED_REQUIREMENT_KEYS = (PIPELINE_KEY, JOB_JSON_KEY)


def reserved_extras(requirements: dict[str, Any] | None) -> dict[str, Any]:
    blob = requirements if isinstance(requirements, dict) else {}
    return {key: blob[key] for key in RESERVED_REQUIREMENT_KEYS if key in blob}


def persist_blob(fields: dict[str, Any], *, extras: dict[str, Any] | None = None) -> dict[str, Any]:
    blob = dict(fields["requirements"])
    if extras:
        blob.update(extras)
    return blob


def validate_for_publish(doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not str(doc.get("title") or "").strip():
        errors.append("Job Title is required")
    if not str(doc.get("description") or "").strip():
        errors.append("Job Description is required")
    skills = doc.get("required_skills") or (doc.get("requirements") or {}).get("skills") or []
    if not skills:
        errors.append("At least one required skill is required")
    if not str(doc.get("location") or "").strip():
        errors.append("Location is required")
    if not str(doc.get("employment_type") or "").strip():
        errors.append("Employment Type is required")
    return errors
