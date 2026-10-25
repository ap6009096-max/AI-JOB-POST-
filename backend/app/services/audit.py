from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import AuditLog
from app.db.repositories import AuditRepository


class AuditService:
    def __init__(self, session: Session) -> None:
        self._repo = AuditRepository(session)

    def get(self, log_id: UUID) -> AuditLog | None:
        return self._repo.get(log_id)

    def list(self, *, actor_user_id: UUID | None = None, limit: int = 100, offset: int = 0) -> list[AuditLog]:
        return self._repo.list(actor_user_id=actor_user_id, limit=limit, offset=offset)

    def create(
        self,
        *,
        action: str,
        entity_type: str,
        actor_user_id: UUID | None = None,
        entity_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> AuditLog:
        return self._repo.create(
            action=action,
            entity_type=entity_type,
            actor_user_id=actor_user_id,
            entity_id=entity_id,
            metadata=metadata,
        )
