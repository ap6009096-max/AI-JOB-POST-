from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Embedding


class EmbeddingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, embedding_id: UUID) -> Embedding | None:
        return self.session.get(Embedding, embedding_id)

    def list(
        self,
        *,
        owner_type: str | None = None,
        owner_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Embedding]:
        stmt = select(Embedding)
        if owner_type is not None:
            stmt = stmt.where(Embedding.owner_type == owner_type)
        if owner_id is not None:
            stmt = stmt.where(Embedding.owner_id == owner_id)
        return list(self.session.scalars(stmt.offset(offset).limit(limit)))

    def get_by_owner(self, *, owner_type: str, owner_id: UUID, model: str) -> Embedding | None:
        return self.session.scalar(
            select(Embedding).where(
                Embedding.owner_type == owner_type,
                Embedding.owner_id == owner_id,
                Embedding.model == model,
            )
        )

    def create(
        self,
        *,
        owner_type: str,
        owner_id: UUID,
        model: str,
        embedding: list[float],
        content_hash: str = "",
    ) -> Embedding:
        row = Embedding(
            owner_type=owner_type,
            owner_id=owner_id,
            model=model,
            embedding=embedding,
            content_hash=content_hash,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def upsert(
        self,
        *,
        owner_type: str,
        owner_id: UUID,
        model: str,
        embedding: list[float],
        content_hash: str = "",
    ) -> Embedding:
        row = self.get_by_owner(owner_type=owner_type, owner_id=owner_id, model=model)
        if row is None:
            return self.create(
                owner_type=owner_type,
                owner_id=owner_id,
                model=model,
                embedding=embedding,
                content_hash=content_hash,
            )
        row.embedding = embedding
        row.content_hash = content_hash
        self.session.flush()
        return row
