from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job, JobSkill


class JobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, job_id: UUID) -> Job | None:
        return self.session.get(Job, job_id)

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Job]:
        return list(self.session.scalars(select(Job).offset(offset).limit(limit)))

    def list_by_company(self, company_id: UUID, *, limit: int = 100, offset: int = 0) -> list[Job]:
        return list(
            self.session.scalars(
                select(Job)
                .where(Job.company_id == company_id)
                .order_by(Job.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )

    def list_by_companies(self, company_ids: list[UUID], *, limit: int = 100, offset: int = 0) -> list[Job]:
        if not company_ids:
            return []
        return list(
            self.session.scalars(
                select(Job)
                .where(Job.company_id.in_(company_ids))
                .order_by(Job.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )

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
        job = Job(
            company_id=company_id,
            title=title,
            description=description,
            location=location,
            status=status,
            requirements=requirements or {},
        )
        self.session.add(job)
        self.session.flush()
        return job

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
        if title is not None:
            job.title = title.strip() or job.title
        if description is not None:
            job.description = description
        if location is not None:
            job.location = location
        if status is not None:
            job.status = status
        if requirements is not None:
            job.requirements = requirements
        self.session.add(job)
        self.session.flush()
        return job

    def add_skill(self, *, job_id: UUID, skill: str, weight: float = 1) -> JobSkill:
        row = JobSkill(job_id=job_id, skill=skill, weight=weight)
        self.session.add(row)
        self.session.flush()
        return row
