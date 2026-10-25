from __future__ import annotations

from typing import Any

COMPLETION_SECTIONS = (
    "profile",
    "resume",
    "experience",
    "education",
    "skills",
    "technologies",
    "projects",
    "certifications",
    "achievements",
    "links",
    "preferences",
)

SECTION_LABELS = {
    "profile": "My Profile",
    "resume": "Resume",
    "experience": "Experience",
    "education": "Education",
    "skills": "Skills",
    "technologies": "Technologies",
    "projects": "Projects",
    "certifications": "Certifications",
    "achievements": "Achievements",
    "links": "Professional Links",
    "preferences": "Preferences",
}


def _filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _extras_list(extras: dict, key: str) -> list:
    value = extras.get(key)
    return value if isinstance(value, list) else []


def completion_flags(
    *,
    headline: str = "",
    location: str = "",
    extras: dict | None = None,
    experience_count: int = 0,
    education_count: int = 0,
    skill_count: int = 0,
    project_count: int = 0,
    certification_count: int = 0,
    link_count: int = 0,
) -> dict[str, bool]:
    extras = extras or {}
    resume = extras.get("resume") if isinstance(extras.get("resume"), dict) else {}
    preferences = extras.get("preferences") if isinstance(extras.get("preferences"), dict) else {}
    personal = extras.get("personal") if isinstance(extras.get("personal"), dict) else {}
    named_profile = (
        _filled(personal.get("given_name"))
        and _filled(personal.get("family_name"))
        and _filled(personal.get("city"))
        and _filled(headline)
    )
    fallback_profile = _filled(headline) and _filled(location)
    return {
        "profile": named_profile or fallback_profile,
        "resume": _filled(resume.get("text")) or _filled(resume.get("url")),
        "experience": experience_count >= 1,
        "education": education_count >= 1,
        "skills": skill_count >= 1,
        "technologies": len(_extras_list(extras, "technologies")) >= 1,
        "projects": project_count >= 1,
        "certifications": certification_count >= 1,
        "achievements": len(_extras_list(extras, "achievements")) >= 1,
        "links": link_count >= 1,
        "preferences": preferences.get("open_to_work") is not None or _filled(preferences.get("work_mode")),
    }


def completion_percent(flags: dict[str, bool]) -> int:
    if not flags:
        return 0
    done = sum(1 for key in COMPLETION_SECTIONS if flags.get(key))
    return round(100 * done / len(COMPLETION_SECTIONS))


def intelligence(flags: dict[str, bool], *, skill_count: int, experience_count: int) -> dict[str, Any]:
    missing = [key for key in COMPLETION_SECTIONS if not flags.get(key)]
    if missing:
        next_action = f"Add {SECTION_LABELS[missing[0]]}"
    else:
        next_action = "Review your profile"
    return {
        "missing_sections": missing,
        "next_action": next_action,
        "skill_count": skill_count,
        "experience_count": experience_count,
    }
