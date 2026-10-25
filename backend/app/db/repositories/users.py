from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, user_id: UUID) -> User | None:
        return self.session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email))

    def get_by_auth_user_id(self, auth_user_id: UUID) -> User | None:
        return self.session.scalar(select(User).where(User.auth_user_id == auth_user_id))

    def list(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        return list(self.session.scalars(select(User).offset(offset).limit(limit)))

    def create(
        self,
        *,
        email: str,
        full_name: str = "",
        status: str = "active",
        auth_user_id: UUID | None = None,
        role: str | None = None,
    ) -> User:
        user = User(
            email=email,
            full_name=full_name,
            status=status,
            auth_user_id=auth_user_id,
            role=role,
        )
        self.session.add(user)
        self.session.flush()
        return user
