from __future__ import annotations

import re
from typing import Any

from app.data.skill_aliases import canonical_set, canonical_skill


SCORE_VERSION = "match-score-v2"
SCORE_WEIGHTS = {
    "skills": 0.34,
    "experience": 0.22,
    "projects": 0.13,
    "technology": 0.12,
    "semantic": 0.11,
    "education": 0.08,
}
PREFERRED_SKILL_WEIGHT = 0.5
SIDE_SCORES = ("location", "salary")
COMPONENT_SCORES = (
    "skills",
    "experience",
    "projects",
    "education",
    "semantic",
    "technology",
    "location",
    "salary",
)

_AMOUNT = re.compile(r"(?<![A-Za-z])(\d+(?:,\d{3})*(?:\.\d+)?)\s*([kK])?")


def _norm(value: str) -> str:
    return value.strip().lower()


def skill_score(required: list[str], actual: list[str]) -> float:
    if not required:
        return 1.0
    required_set = canonical_set(required)
    actual_set = canonical_set(actual)
    if not required_set:
        return 1.0
    return len(required_set & actual_set) / len(required_set)


def combined_skill_score(required: list[str], preferred: list[str], actual: list[str]) -> float:
    required_clean = [str(item).strip() for item in required if str(item).strip()]
    preferred_clean = [str(item).strip() for item in preferred if str(item).strip()]
    if not required_clean and not preferred_clean:
        return 1.0
    if not required_clean:
        return skill_score(preferred_clean, actual)
    if not preferred_clean:
        return skill_score(required_clean, actual)
    return (
        skill_score(required_clean, actual) + PREFERRED_SKILL_WEIGHT * skill_score(preferred_clean, actual)
    ) / (1.0 + PREFERRED_SKILL_WEIGHT)


def requirement_overlap(required: list[str], actual: list[str]) -> tuple[list[str], list[str]]:
    actual_keys = canonical_set(actual)
    matched: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()
    for item in required:
        label = str(item).strip()
        if not label:
            continue
        key = canonical_skill(label)
        if not key or key in seen:
            continue
        seen.add(key)
        if key in actual_keys:
            matched.append(label)
        else:
            missing.append(label)
    return matched, missing


def experience_score(required_years: float, actual_years: float) -> float:
    if required_years <= 0:
        return 1.0
    return min(max(actual_years, 0.0) / required_years, 1.0)


def keyword_score(job: dict[str, Any], profile: dict[str, Any]) -> float:
    tokens = set()
    for raw in job.get("requirements", {}).get("keywords", []):
        tokens.add(_norm(str(raw)))
    title = _norm(str(job.get("title", "")))
    tokens.update(part for part in re.split(r"\W+", title) if len(part) > 2)

    haystack = " ".join(
        [
            str(profile.get("title", "")),
            str(profile.get("resume_summary", "")),
            " ".join(str(skill) for skill in profile.get("skills", [])),
        ]
    ).lower()
    if not tokens:
        return 0.0
    hits = sum(1 for token in tokens if token in haystack)
    return hits / len(tokens)


def location_score(required: str, actual: str) -> float:
    if not required:
        return 1.0
    required_n = _norm(required)
    actual_n = _norm(actual)
    if not actual_n:
        return 0.0
    if required_n in actual_n or actual_n in required_n:
        return 1.0
    return 0.0


def project_score(job: dict[str, Any], profile: dict[str, Any]) -> float:
    tokens = canonical_set(_job_skills(job) + list(job.get("technologies") or []))
    if not tokens:
        return 1.0
    haystack = _project_haystack(profile)
    if not haystack.strip():
        return 0.0
    haystack_n = _norm(haystack)
    haystack_keys = {canonical_skill(part) for part in re.split(r"\W+", haystack_n) if part}
    hits = sum(1 for token in tokens if token and (token in haystack_n or token in haystack_keys))
    return hits / len(tokens)


def education_score(required: str, profile: dict[str, Any]) -> float:
    required_n = _norm(required)
    if not required_n:
        return 1.0
    haystack = _education_haystack(profile).lower()
    if not haystack.strip():
        return 0.0
    if required_n in haystack or haystack in required_n:
        return 1.0
    tokens = [part for part in re.split(r"\W+", required_n) if len(part) > 2]
    if not tokens:
        return 0.0
    hits = sum(1 for token in tokens if token in haystack)
    return hits / len(tokens)


def technology_score(required: list[str], actual: list[str]) -> float:
    return skill_score(required, actual)


def semantic_score(similarity: float | None) -> float:
    if similarity is None:
        return 0.0
    return min(max(float(similarity), 0.0), 1.0)


def salary_score(job_salary: str, candidate_salary: str) -> float:
    job_range = _salary_range(job_salary)
    candidate_range = _salary_range(candidate_salary)
    if job_range is None or candidate_range is None:
        return 0.5
    low = max(job_range[0], candidate_range[0])
    high = min(job_range[1], candidate_range[1])
    if high >= low:
        return 1.0
    gap = min(abs(candidate_range[1] - job_range[0]), abs(job_range[1] - candidate_range[0]))
    span = max(job_range[1] - job_range[0], candidate_range[1] - candidate_range[0], 1.0)
    return min(max(1.0 - gap / span, 0.0), 1.0)


def location_score_profile(required: str, profile: dict[str, Any]) -> float:
    if not required:
        return 1.0
    required_n = _norm(required)
    actuals = [str(profile.get("location") or "")]
    preferences = profile.get("preferences") if isinstance(profile.get("preferences"), dict) else {}
    locations = preferences.get("locations") or []
    if isinstance(locations, list):
        actuals.extend(str(item) for item in locations)
    if "remote" in required_n and (
        preferences.get("work_mode") == "remote" or preferences.get("remote") is True
    ):
        return 1.0
    return max(location_score(required, value) for value in actuals) if actuals else 0.0


def compare_candidate(job: dict[str, Any], profile: dict[str, Any]) -> dict[str, float]:
    requirements = job.get("requirements", {})
    skills = skill_score(list(requirements.get("skills", [])), list(profile.get("skills", [])))
    experience = experience_score(
        float(requirements.get("experience_years", 0) or 0),
        float(profile.get("experience_years", 0) or 0),
    )
    keywords = keyword_score(job, profile)
    location = location_score(str(requirements.get("location", "")), str(profile.get("location", "")))
    return {
        "skills": round(skills, 4),
        "experience": round(experience, 4),
        "keywords": round(keywords, 4),
        "location": round(location, 4),
    }


def compare_portal_candidate(
    job: dict[str, Any],
    profile: dict[str, Any],
    *,
    semantic: float | None = 0.0,
) -> dict[str, float]:
    requirements = job.get("requirements", {}) if isinstance(job.get("requirements"), dict) else {}
    experience_required = 0.0
    job_experience = job.get("experience")
    if isinstance(job_experience, dict):
        experience_required = float(job_experience.get("years") or 0)
    if not experience_required:
        experience_required = float(requirements.get("experience_years") or 0)
    location_required = str(job.get("location") or requirements.get("location") or "")
    return {
        "skills": round(
            combined_skill_score(
                _job_skills(job),
                _job_preferred(job),
                list(profile.get("skills") or []),
            ),
            4,
        ),
        "experience": round(
            experience_score(experience_required, float(profile.get("experience_years") or 0)),
            4,
        ),
        "projects": round(project_score(job, profile), 4),
        "education": round(education_score(str(job.get("education") or ""), profile), 4),
        "technology": round(
            technology_score(list(job.get("technologies") or []), list(profile.get("technologies") or [])),
            4,
        ),
        "semantic": round(semantic_score(semantic), 4),
        "location": round(location_score_profile(location_required, profile), 4),
        "salary": round(
            salary_score(str(job.get("salary_range") or ""), str(profile.get("salary_expectation") or "")),
            4,
        ),
    }


def score_match(
    job: dict[str, Any],
    profile: dict[str, Any],
    *,
    semantic: float | None = 0.0,
) -> dict[str, Any]:
    parts = compare_portal_candidate(job, profile, semantic=semantic)
    return {
        "score": weighted_score(parts, SCORE_WEIGHTS),
        "parts": parts,
        "weights": dict(SCORE_WEIGHTS),
        "version": SCORE_VERSION,
    }


def numeric_parts(parts: dict[str, Any]) -> dict[str, float]:
    return {key: float(parts[key]) for key in COMPONENT_SCORES if key in parts}


def weighted_score(parts: dict[str, float], weights: dict[str, float]) -> float:
    total = sum(weights.values()) or 1.0
    return round(sum(float(parts.get(key, 0.0)) * weights[key] for key in weights) / total, 4)


def _job_skills(job: dict[str, Any]) -> list[str]:
    skills = list(job.get("required_skills") or [])
    if skills:
        return skills
    requirements = job.get("requirements") if isinstance(job.get("requirements"), dict) else {}
    return list(requirements.get("skills") or [])


def _job_preferred(job: dict[str, Any]) -> list[str]:
    preferred = list(job.get("preferred_skills") or [])
    if preferred:
        return preferred
    requirements = job.get("requirements") if isinstance(job.get("requirements"), dict) else {}
    return list(requirements.get("preferred_skills") or [])


def _project_haystack(profile: dict[str, Any]) -> str:
    parts: list[str] = []
    for project in profile.get("projects") or []:
        if isinstance(project, dict):
            parts.append(str(project.get("name") or ""))
            parts.append(str(project.get("description") or ""))
        else:
            parts.append(str(project))
    return " ".join(parts)


def _education_haystack(profile: dict[str, Any]) -> str:
    parts: list[str] = []
    education = profile.get("education")
    if isinstance(education, str):
        parts.append(education)
    elif isinstance(education, list):
        for row in education:
            if isinstance(row, dict):
                parts.extend(
                    [
                        str(row.get("school") or ""),
                        str(row.get("degree") or ""),
                        str(row.get("field_of_study") or ""),
                    ]
                )
            else:
                parts.append(str(row))
    return " ".join(parts)


def _salary_amounts(text: str) -> list[float]:
    values: list[float] = []
    for match in _AMOUNT.finditer(str(text or "").replace("–", "-").replace("—", "-")):
        raw = match.group(1).replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        if match.group(2):
            value *= 1000
        values.append(value)
    return values


def _salary_range(text: str) -> tuple[float, float] | None:
    amounts = _salary_amounts(text)
    if not amounts:
        return None
    return min(amounts), max(amounts)
