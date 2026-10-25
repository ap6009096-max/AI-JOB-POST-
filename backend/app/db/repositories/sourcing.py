from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ExternalCandidate, SourceEvidence, SourcingRun


class SourcingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, run_id: UUID) -> SourcingRun | None:
        return self.session.get(SourcingRun, run_id)

    def get_external_candidate(self, candidate_id: UUID) -> ExternalCandidate | None:
        return self.session.get(ExternalCandidate, candidate_id)

    def list(self, *, job_id: UUID | None = None, limit: int = 100, offset: int = 0) -> list[SourcingRun]:
        stmt = select(SourcingRun)
        if job_id is not None:
            stmt = stmt.where(SourcingRun.job_id == job_id)
        return list(self.session.scalars(stmt.offset(offset).limit(limit)))

    def create(self, *, job_id: UUID, status: str = "pending", query: dict | None = None) -> SourcingRun:
        run = SourcingRun(job_id=job_id, status=status, query=query or {})
        self.session.add(run)
        self.session.flush()
        return run

    def create_external_candidate(
        self,
        *,
        sourcing_run_id: UUID,
        source: str,
        url: str | None = None,
        display_name: str = "",
        payload: dict | None = None,
    ) -> ExternalCandidate:
        row = ExternalCandidate(
            sourcing_run_id=sourcing_run_id,
            source=source,
            url=url,
            display_name=display_name,
            payload=payload or {},
        )
        self.session.add(row)
        self.session.flush()
        return row

    def create_evidence(
        self,
        *,
        external_candidate_id: UUID,
        kind: str,
        body: dict | None = None,
    ) -> SourceEvidence:
        row = SourceEvidence(
            external_candidate_id=external_candidate_id,
            kind=kind,
            body=body or {},
        )
        self.session.add(row)
        self.session.flush()
        return row
