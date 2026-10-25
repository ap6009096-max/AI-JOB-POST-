from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditLog


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, log_id: UUID) -> AuditLog | None:
        return self.session.get(AuditLog, log_id)

    def list(
        self,
        *,
        actor_user_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        stmt = select(AuditLog)
        if actor_user_id is not None:
            stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
        return list(self.session.scalars(stmt.offset(offset).limit(limit)))

    def create(
        self,
        *,
        action: str,
        entity_type: str,
        actor_user_id: UUID | None = None,
        entity_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> AuditLog:
        row = AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_=metadata or {},
        )
        self.session.add(row)
        self.session.flush()
        return row
