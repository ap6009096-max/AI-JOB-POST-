from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

from app.data.seed import (
    DEMO_COMPANY,
    DEMO_JOB,
    EXTERNAL_CANDIDATES,
    PORTAL_CANDIDATES,
)


class TalentStore:
    def __init__(self) -> None:
        self.company = deepcopy(DEMO_COMPANY)
        self.jobs = {DEMO_JOB["id"]: deepcopy(DEMO_JOB)}
        self.portal_candidates = {item["id"]: deepcopy(item) for item in PORTAL_CANDIDATES}
        self.external_candidates = {item["id"]: deepcopy(item) for item in EXTERNAL_CANDIDATES}
        self.ranking_runs: dict[str, dict] = {}

    def list_jobs(self) -> list[dict]:
        return list(self.jobs.values())

    def get_job(self, job_id: str) -> dict | None:
        return self.jobs.get(job_id)

    def list_portal(self) -> list[dict]:
        return list(self.portal_candidates.values())

    def list_external(self) -> list[dict]:
        return list(self.external_candidates.values())

    def merge_reddit_externals(self, items: list[dict]) -> None:
        for item in items:
            candidate_id = str(item.get("id") or "")
            if not candidate_id.startswith("reddit-"):
                continue
            self.external_candidates[candidate_id] = deepcopy(item)

    def get_portal(self, candidate_id: str) -> dict | None:
        return self.portal_candidates.get(candidate_id)

    def get_external(self, candidate_id: str) -> dict | None:
        return self.external_candidates.get(candidate_id)

    def save_run(self, job_id: str, track: str, limit: int, results: list[dict]) -> dict:
        run = {
            "id": str(uuid4()),
            "job_id": job_id,
            "track": track,
            "limit": limit,
            "results": results,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self.ranking_runs[run["id"]] = run
        return run

    def get_run(self, job_id: str, run_id: str) -> dict | None:
        run = self.ranking_runs.get(run_id)
        if run is None or run["job_id"] != job_id:
            return None
        return run


store = TalentStore()
