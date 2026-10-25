from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import MatchingRun
from app.db.repositories import MatchingRepository
from app.services.comparison import SCORE_VERSION, SCORE_WEIGHTS, numeric_parts
from app.services.match_result import build_match_result


class MatchingService:
    def __init__(self, session: Session) -> None:
        self._repo = MatchingRepository(session)

    def get(self, run_id: UUID) -> MatchingRun | None:
        return self._repo.get(run_id)

    def list(self, *, job_id: UUID | None = None, limit: int = 100, offset: int = 0) -> list[MatchingRun]:
        return self._repo.list(job_id=job_id, limit=limit, offset=offset)

    def list_for_companies(
        self, company_ids: list[UUID], *, limit: int = 100, offset: int = 0
    ) -> list[MatchingRun]:
        return self._repo.list_for_companies(company_ids, limit=limit, offset=offset)

    def latest_for_job(self, job_id: UUID, track: str) -> MatchingRun | None:
        return self._repo.latest_for_job(job_id, track)

    def create(self, *, job_id: UUID, track: str, status: str = "pending", params: dict | None = None) -> MatchingRun:
        return self._repo.create(job_id=job_id, track=track, status=status, params=params)

    def persist_portal_run(self, *, job_id: UUID, limit: int, results: list[dict]) -> MatchingRun:
        run = self.create(
            job_id=job_id,
            track="portal",
            status="completed",
            params={
                "limit": limit,
                "results": results,
                "calculation_version": SCORE_VERSION,
            },
        )
        for row in results:
            candidate_id = UUID(str(row["candidate_id"]))
            score = float(row["score"])
            document = build_match_result(
                job_id=str(job_id),
                matching_run_id=str(run.id),
                source_type="portal",
                row=row,
            )
            row["match_result"] = document
            self._repo.create_score(
                run_id=run.id,
                candidate_id=candidate_id,
                score=score,
                parts={
                    **numeric_parts(dict(row.get("parts") or {})),
                    "version": str(row.get("calculation_version") or SCORE_VERSION),
                    "weights": dict(SCORE_WEIGHTS),
                    "narrative": row.get("narrative"),
                    "matched_requirements": list(row.get("matched_requirements") or []),
                    "missing_requirements": list(row.get("missing_requirements") or []),
                    "source": row.get("source"),
                    "match_result": document,
                },
            )
            self._repo.create_result(
                run_id=run.id,
                rank=int(row["rank"]),
                score=score,
                candidate_id=candidate_id,
            )
        return run

    def persist_internet_run(
        self,
        *,
        job_id: UUID,
        limit: int,
        results: list[dict],
        extra_params: dict | None = None,
    ) -> MatchingRun:
        params = {
            "limit": limit,
            "results": results,
            **(extra_params or {}),
            "calculation_version": SCORE_VERSION,
        }
        run = self.create(job_id=job_id, track="internet", status="completed", params=params)
        for row in results:
            document = build_match_result(
                job_id=str(job_id),
                matching_run_id=str(run.id),
                source_type="internet",
                row=row,
            )
            row["match_result"] = document
            try:
                external_id = UUID(str(row["candidate_id"]))
            except ValueError:
                continue
            score = float(row["score"])
            self._repo.create_score(
                run_id=run.id,
                external_candidate_id=external_id,
                score=score,
                parts={
                    **numeric_parts(dict(row.get("parts") or {})),
                    "version": str(row.get("calculation_version") or SCORE_VERSION),
                    "weights": dict(SCORE_WEIGHTS),
                    "narrative": row.get("narrative"),
                    "matched_requirements": list(row.get("matched_requirements") or []),
                    "missing_requirements": list(row.get("missing_requirements") or []),
                    "source": row.get("source"),
                    "reasons": list(row.get("reasons") or []),
                    "identity_status": row.get("identity_status"),
                    "match_result": document,
                },
            )
            self._repo.create_result(
                run_id=run.id,
                rank=int(row["rank"]),
                score=score,
                external_candidate_id=external_id,
            )
        return run
