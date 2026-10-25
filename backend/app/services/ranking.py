from __future__ import annotations

from typing import Any

from app.services.comparison import compare_candidate, weighted_score

PORTAL_WEIGHTS = {
    "skills": 0.50,
    "experience": 0.25,
    "keywords": 0.15,
    "location": 0.10,
}

AI_WEIGHTS = {
    "skills": 0.40,
    "experience": 0.20,
    "keywords": 0.25,
    "location": 0.15,
}


def _reasons(parts: dict[str, float], engine: str) -> list[str]:
    ordered = sorted(parts.items(), key=lambda item: item[1], reverse=True)
    labels = {
        "skills": "skills overlap with the job",
        "experience": "years of experience vs requirement",
        "keywords": "title and keyword match",
        "location": "location fit",
    }
    prefix = "Ranking engine" if engine == "portal" else "AI ranking stub"
    return [f"{prefix}: {labels[key]} ({value:.0%})" for key, value in ordered[:3]]


def _rank(
    job: dict[str, Any],
    candidates: list[dict[str, Any]],
    limit: int,
    weights: dict[str, float],
    engine: str,
) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for candidate in candidates:
        profile = candidate["profile"]
        parts = compare_candidate(job, profile)
        scored.append(
            {
                "candidate_id": candidate["id"],
                "name": profile.get("name", ""),
                "title": profile.get("title", ""),
                "source": profile.get("source"),
                "identity_status": profile.get("identity_status"),
                "location": profile.get("location", ""),
                "score": weighted_score(parts, weights),
                "parts": parts,
                "reasons": _reasons(parts, engine),
            }
        )
    scored.sort(key=lambda row: (-row["score"], row["name"]))
    limited = scored[:limit]
    for index, row in enumerate(limited, start=1):
        row["rank"] = index
    return limited


class RankingEngine:
    def rank(self, job: dict[str, Any], candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        return _rank(job, candidates, limit, PORTAL_WEIGHTS, "portal")


class AIRankingStub:
    def rank(self, job: dict[str, Any], candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        return _rank(job, candidates, limit, AI_WEIGHTS, "internet")
