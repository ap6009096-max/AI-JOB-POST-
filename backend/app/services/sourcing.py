from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import ExternalCandidate, SourceEvidence, SourcingRun
from app.db.repositories import SourcingRepository


class SourcingService:
    def __init__(self, session: Session) -> None:
        self._repo = SourcingRepository(session)

    def get(self, run_id: UUID) -> SourcingRun | None:
        return self._repo.get(run_id)

    def get_external_candidate(self, candidate_id: UUID) -> ExternalCandidate | None:
        return self._repo.get_external_candidate(candidate_id)

    def list(self, *, job_id: UUID | None = None, limit: int = 100, offset: int = 0) -> list[SourcingRun]:
        return self._repo.list(job_id=job_id, limit=limit, offset=offset)

    def create(self, *, job_id: UUID, status: str = "pending", query: dict | None = None) -> SourcingRun:
        return self._repo.create(job_id=job_id, status=status, query=query)

    def complete(self, run: SourcingRun, *, query: dict | None = None) -> SourcingRun:
        run.status = "completed"
        if query is not None:
            run.query = query
        self._repo.session.flush()
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
        return self._repo.create_external_candidate(
            sourcing_run_id=sourcing_run_id,
            source=source,
            url=url,
            display_name=display_name,
            payload=payload,
        )

    def create_evidence(
        self,
        *,
        external_candidate_id: UUID,
        kind: str,
        body: dict | None = None,
    ) -> SourceEvidence:
        return self._repo.create_evidence(
            external_candidate_id=external_candidate_id,
            kind=kind,
            body=body,
        )
