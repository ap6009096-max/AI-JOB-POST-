from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Company, CompanyUser
from app.db.repositories import CompanyRepository


class CompanyService:
    def __init__(self, session: Session) -> None:
        self._repo = CompanyRepository(session)

    def get(self, company_id: UUID) -> Company | None:
        return self._repo.get(company_id)

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Company]:
        return self._repo.list(limit=limit, offset=offset)

    def create(self, *, name: str, website: str | None = None, extras: dict | None = None) -> Company:
        return self._repo.create(name=name, website=website, extras=extras)

    def add_member(self, *, company_id: UUID, user_id: UUID, role: str) -> CompanyUser:
        return self._repo.add_member(company_id=company_id, user_id=user_id, role=role)

    def list_members(self, company_id: UUID) -> list[CompanyUser]:
        return self._repo.list_members(company_id)

    def update(
        self,
        company: Company,
        *,
        name: str | None = None,
        extras_patch: dict | None = None,
    ) -> Company:
        return self._repo.update(company, name=name, extras_patch=extras_patch)
