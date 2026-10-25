from app.data.seed import DEMO_JOB, PORTAL_CANDIDATES
from app.services.comparison import (
    PREFERRED_SKILL_WEIGHT,
    SCORE_VERSION,
    SCORE_WEIGHTS,
    combined_skill_score,
    compare_candidate,
    compare_portal_candidate,
    requirement_overlap,
    salary_score,
    score_match,
    skill_score,
)
from app.services.ranking import RankingEngine


def test_perfect_skill_overlap() -> None:
    required = DEMO_JOB["requirements"]["skills"]
    actual = PORTAL_CANDIDATES[0]["profile"]["skills"]
    assert skill_score(required, actual) == 1.0


def test_zero_skill_overlap() -> None:
    required = ["Python", "TypeScript"]
    assert skill_score(required, ["Figma"]) == 0.0


def test_skill_aliases_match_common_variants() -> None:
    assert skill_score(["React"], ["React.js"]) == 1.0
    assert skill_score(["TypeScript", "PostgreSQL"], ["TS", "Postgres"]) == 1.0
    assert skill_score(["Node.js"], ["Node"]) == 1.0


def test_preferred_skills_have_half_weight() -> None:
    required = ["Python"]
    preferred = ["TypeScript"]
    actual = ["Python"]
    expected = (1.0 + PREFERRED_SKILL_WEIGHT * 0.0) / (1.0 + PREFERRED_SKILL_WEIGHT)
    assert combined_skill_score(required, preferred, actual) == expected
    assert combined_skill_score(required, [], actual) == 1.0


def test_comparison_parts_are_bounded() -> None:
    parts = compare_candidate(DEMO_JOB, PORTAL_CANDIDATES[12]["profile"])
    assert set(parts) == {"skills", "experience", "keywords", "location"}
    assert all(0.0 <= value <= 1.0 for value in parts.values())


def test_ranking_engine_respects_top_n() -> None:
    engine = RankingEngine()
    results = engine.rank(DEMO_JOB, PORTAL_CANDIDATES, 10)
    assert len(results) == 10
    scores = [row["score"] for row in results]
    assert scores == sorted(scores, reverse=True)
    assert [row["rank"] for row in results] == list(range(1, 11))


_PORTAL_PROFILE = {
    "skills": ["Python", "FastAPI"],
    "technologies": ["FastAPI"],
    "experience_years": 4,
    "projects": [{"name": "Hiring API", "description": "Python FastAPI service"}],
    "education": [{"school": "NIT", "degree": "B.Tech", "field_of_study": "Computer Science"}],
    "location": "Bengaluru",
    "salary_expectation": "",
    "preferences": {},
}

_PORTAL_JOB = {
    **DEMO_JOB,
    "required_skills": DEMO_JOB["requirements"]["skills"],
    "technologies": ["FastAPI"],
    "education": "Computer Science",
    "salary_range": "15 LPA",
    "experience": {"years": 5, "text": ""},
}


def test_portal_comparison_parts_and_weights() -> None:
    parts = compare_portal_candidate(_PORTAL_JOB, _PORTAL_PROFILE, semantic=0.8)
    assert set(parts) == {
        "skills",
        "experience",
        "projects",
        "education",
        "technology",
        "semantic",
        "location",
        "salary",
    }
    assert all(0.0 <= value <= 1.0 for value in parts.values())
    assert parts["semantic"] == 0.8
    assert parts["salary"] == 0.5
    assert abs(sum(SCORE_WEIGHTS.values()) - 1.0) < 1e-9


def test_score_match_uses_v2_weights() -> None:
    match = score_match(_PORTAL_JOB, _PORTAL_PROFILE, semantic=0.8)
    parts = match["parts"]
    expected = round(
        parts["skills"] * 0.34
        + parts["experience"] * 0.22
        + parts["projects"] * 0.13
        + parts["technology"] * 0.12
        + parts["semantic"] * 0.11
        + parts["education"] * 0.08,
        4,
    )
    assert match["score"] == expected
    assert match["version"] == "match-score-v2"
    assert match["version"] == SCORE_VERSION
    assert match["weights"] == SCORE_WEIGHTS


def test_technology_changes_total() -> None:
    other = {**_PORTAL_PROFILE, "technologies": ["Java"]}
    base = score_match(_PORTAL_JOB, _PORTAL_PROFILE, semantic=0.5)
    changed = score_match(_PORTAL_JOB, other, semantic=0.5)
    assert base["parts"]["technology"] != changed["parts"]["technology"]
    assert base["score"] != changed["score"]


def test_side_scores_do_not_change_total() -> None:
    other = {
        **_PORTAL_PROFILE,
        "location": "Tokyo",
        "salary_expectation": "5 LPA",
    }
    base = score_match(_PORTAL_JOB, _PORTAL_PROFILE, semantic=0.5)
    changed = score_match(_PORTAL_JOB, other, semantic=0.5)
    assert base["score"] == changed["score"]
    assert base["parts"]["location"] != changed["parts"]["location"]
    assert base["parts"]["salary"] != changed["parts"]["salary"]


def test_salary_score_neutral_when_missing() -> None:
    assert salary_score("", "12 LPA") == 0.5
    assert salary_score("12 LPA", "") == 0.5
    assert salary_score("12-18 LPA", "15 LPA") == 1.0


def test_requirement_overlap_keeps_job_labels() -> None:
    matched, missing = requirement_overlap(["Python", "TypeScript", "python"], ["python", "FastAPI"])
    assert matched == ["Python"]
    assert missing == ["TypeScript"]


def test_requirement_overlap_matches_aliases() -> None:
    matched, missing = requirement_overlap(["React.js", "TypeScript"], ["React", "TS"])
    assert matched == ["React.js", "TypeScript"]
    assert missing == []
