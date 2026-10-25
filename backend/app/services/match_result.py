from __future__ import annotations

from typing import Any, Literal

from app.services.privacy import strip_protected_disclosures

SCORE_KEYS = {
    "skill_match_score": "skills",
    "experience_match_score": "experience",
    "project_match_score": "projects",
    "education_match_score": "education",
    "technology_match_score": "technology",
    "semantic_match_score": "semantic",
    "location_match_score": "location",
    "salary_match_score": "salary",
}


def build_match_result(
    *,
    job_id: str,
    matching_run_id: str,
    source_type: Literal["portal", "internet"],
    row: dict[str, Any],
) -> dict[str, Any]:
    parts = dict(row.get("parts") or {})
    narrative = row.get("narrative") if isinstance(row.get("narrative"), dict) else {}
    reasons = [str(item) for item in (row.get("reasons") or []) if item]
    source = str(row.get("source") or ("AI Job Post Portal" if source_type == "portal" else "Internet"))
    overall = float(row.get("score") or 0.0)
    if source_type == "internet" and row.get("confidence") is not None:
        confidence = float(row.get("confidence") or 0.0)
    else:
        confidence = overall
    document = {
        "job_id": job_id,
        "candidate_id": str(row.get("candidate_id") or ""),
        "matching_run_id": matching_run_id,
        "source_type": source_type,
        "source": source,
        "overall_match_score": overall,
        **{field: float(parts.get(part_key) or 0.0) for field, part_key in SCORE_KEYS.items()},
        "matched_requirements": [str(item) for item in (row.get("matched_requirements") or []) if item],
        "missing_requirements": [str(item) for item in (row.get("missing_requirements") or []) if item],
        "strengths": [str(item) for item in (narrative.get("strengths") or []) if item],
        "weaknesses": [str(item) for item in (narrative.get("weaknesses") or []) if item],
        "evidence": str(narrative.get("evidence") or ""),
        "match_reasoning": str(narrative.get("explanation") or " ".join(reasons)),
        "recommendation": str(narrative.get("recommendation") or ""),
        "confidence_score": confidence,
    }
    return strip_protected_disclosures(document)


def find_result_row(results: list[dict[str, Any]], candidate_id: str) -> dict[str, Any] | None:
    target = str(candidate_id)
    for row in results:
        if str(row.get("candidate_id") or "") == target:
            return row
    return None
