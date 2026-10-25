from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Job
from app.db.repositories import JobRepository


class JobService:
    def __init__(self, session: Session) -> None:
        self._repo = JobRepository(session)

    def get(self, job_id: UUID) -> Job | None:
        return self._repo.get(job_id)

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Job]:
        return self._repo.list(limit=limit, offset=offset)

    def list_by_company(self, company_id: UUID, *, limit: int = 100, offset: int = 0) -> list[Job]:
        return self._repo.list_by_company(company_id, limit=limit, offset=offset)

    def list_by_companies(self, company_ids: list[UUID], *, limit: int = 100, offset: int = 0) -> list[Job]:
        return self._repo.list_by_companies(company_ids, limit=limit, offset=offset)

    def create(
        self,
        *,
        company_id: UUID,
        title: str,
        description: str = "",
        location: str = "",
        status: str = "draft",
        requirements: dict | None = None,
    ) -> Job:
        return self._repo.create(
            company_id=company_id,
            title=title,
            description=description,
            location=location,
            status=status,
            requirements=requirements,
        )

    def update(
        self,
        job: Job,
        *,
        title: str | None = None,
        description: str | None = None,
        location: str | None = None,
        status: str | None = None,
        requirements: dict | None = None,
    ) -> Job:
        return self._repo.update(
            job,
            title=title,
            description=description,
            location=location,
            status=status,
            requirements=requirements,
        )
