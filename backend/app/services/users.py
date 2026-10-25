from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import User
from app.db.repositories import UserRepository


class UserService:
    def __init__(self, session: Session) -> None:
        self._repo = UserRepository(session)

    def get(self, user_id: UUID) -> User | None:
        return self._repo.get(user_id)

    def list(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        return self._repo.list(limit=limit, offset=offset)

    def create(self, *, email: str, full_name: str = "", status: str = "active") -> User:
        return self._repo.create(email=email, full_name=full_name, status=status)
