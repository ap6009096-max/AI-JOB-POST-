from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import CandidateMatchScore, Job, MatchingRun, MatchResult


class MatchingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, run_id: UUID) -> MatchingRun | None:
        return self.session.get(MatchingRun, run_id)

    def list(self, *, job_id: UUID | None = None, limit: int = 100, offset: int = 0) -> list[MatchingRun]:
        stmt = select(MatchingRun).options(joinedload(MatchingRun.job)).order_by(MatchingRun.created_at.desc())
        if job_id is not None:
            stmt = stmt.where(MatchingRun.job_id == job_id)
        return list(self.session.scalars(stmt.offset(offset).limit(limit)).unique())

    def list_for_companies(
        self, company_ids: list[UUID], *, limit: int = 100, offset: int = 0
    ) -> list[MatchingRun]:
        if not company_ids:
            return []
        stmt = (
            select(MatchingRun)
            .join(Job, MatchingRun.job_id == Job.id)
            .where(Job.company_id.in_(company_ids))
            .options(joinedload(MatchingRun.job))
            .order_by(MatchingRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(stmt).unique())

    def latest_for_job(self, job_id: UUID, track: str) -> MatchingRun | None:
        return self.session.scalar(
            select(MatchingRun)
            .where(
                MatchingRun.job_id == job_id,
                MatchingRun.track == track,
                MatchingRun.status == "completed",
            )
            .order_by(MatchingRun.created_at.desc())
            .limit(1)
        )

    def create(
        self,
        *,
        job_id: UUID,
        track: str,
        status: str = "pending",
        params: dict | None = None,
    ) -> MatchingRun:
        run = MatchingRun(job_id=job_id, track=track, status=status, params=params or {})
        self.session.add(run)
        self.session.flush()
        return run

    def create_score(
        self,
        *,
        run_id: UUID,
        score: float,
        candidate_id: UUID | None = None,
        external_candidate_id: UUID | None = None,
        parts: dict | None = None,
    ) -> CandidateMatchScore:
        row = CandidateMatchScore(
            run_id=run_id,
            candidate_id=candidate_id,
            external_candidate_id=external_candidate_id,
            score=score,
            parts=parts or {},
        )
        self.session.add(row)
        self.session.flush()
        return row

    def create_result(
        self,
        *,
        run_id: UUID,
        rank: int,
        score: float,
        candidate_id: UUID | None = None,
        external_candidate_id: UUID | None = None,
    ) -> MatchResult:
        row = MatchResult(
            run_id=run_id,
            rank=rank,
            score=score,
            candidate_id=candidate_id,
            external_candidate_id=external_candidate_id,
        )
        self.session.add(row)
        self.session.flush()
        return row
