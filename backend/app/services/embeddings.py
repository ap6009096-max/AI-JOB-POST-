from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Embedding
from app.db.repositories import EmbeddingRepository


class EmbeddingService:
    def __init__(self, session: Session) -> None:
        self._repo = EmbeddingRepository(session)

    def get(self, embedding_id: UUID) -> Embedding | None:
        return self._repo.get(embedding_id)

    def list(
        self,
        *,
        owner_type: str | None = None,
        owner_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Embedding]:
        return self._repo.list(owner_type=owner_type, owner_id=owner_id, limit=limit, offset=offset)

    def create(
        self,
        *,
        owner_type: str,
        owner_id: UUID,
        model: str,
        embedding: list[float],
        content_hash: str = "",
    ) -> Embedding:
        return self._repo.create(
            owner_type=owner_type,
            owner_id=owner_id,
            model=model,
            embedding=embedding,
            content_hash=content_hash,
        )

    def upsert(
        self,
        *,
        owner_type: str,
        owner_id: UUID,
        model: str,
        embedding: list[float],
        content_hash: str = "",
    ) -> Embedding:
        return self._repo.upsert(
            owner_type=owner_type,
            owner_id=owner_id,
            model=model,
            embedding=embedding,
            content_hash=content_hash,
        )
