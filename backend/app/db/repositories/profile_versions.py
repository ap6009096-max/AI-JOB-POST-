from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import CandidateProfileVersion


class ProfileVersionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, candidate_id: UUID, *, limit: int = 50) -> list[CandidateProfileVersion]:
        stmt = (
            select(CandidateProfileVersion)
            .where(CandidateProfileVersion.candidate_id == candidate_id)
            .order_by(CandidateProfileVersion.version.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def get(self, candidate_id: UUID, version: int) -> CandidateProfileVersion | None:
        return self.session.scalar(
            select(CandidateProfileVersion).where(
                CandidateProfileVersion.candidate_id == candidate_id,
                CandidateProfileVersion.version == version,
            )
        )

    def next_version(self, candidate_id: UUID) -> int:
        current = self.session.scalar(
            select(func.max(CandidateProfileVersion.version)).where(
                CandidateProfileVersion.candidate_id == candidate_id
            )
        )
        return int(current or 0) + 1

    def create(
        self,
        *,
        candidate_id: UUID,
        version: int,
        snapshot: dict,
        change_summary: dict | None = None,
        source: str = "",
    ) -> CandidateProfileVersion:
        row = CandidateProfileVersion(
            candidate_id=candidate_id,
            version=version,
            snapshot=snapshot or {},
            change_summary=change_summary or {},
            source=source,
        )
        self.session.add(row)
        self.session.flush()
        return row
