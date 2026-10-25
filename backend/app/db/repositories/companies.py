from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Company, CompanyUser


class CompanyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, company_id: UUID) -> Company | None:
        return self.session.get(Company, company_id)

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Company]:
        return list(self.session.scalars(select(Company).offset(offset).limit(limit)))

    def create(self, *, name: str, website: str | None = None, extras: dict | None = None) -> Company:
        company = Company(name=name, website=website, extras=extras or {})
        self.session.add(company)
        self.session.flush()
        return company

    def add_member(self, *, company_id: UUID, user_id: UUID, role: str) -> CompanyUser:
        membership = CompanyUser(company_id=company_id, user_id=user_id, role=role)
        self.session.add(membership)
        self.session.flush()
        return membership

    def list_for_user(self, user_id: UUID) -> list[CompanyUser]:
        return list(self.session.scalars(select(CompanyUser).where(CompanyUser.user_id == user_id)))

    def list_members(self, company_id: UUID) -> list[CompanyUser]:
        return list(
            self.session.scalars(select(CompanyUser).where(CompanyUser.company_id == company_id))
        )

    def update(
        self,
        company: Company,
        *,
        name: str | None = None,
        extras_patch: dict | None = None,
    ) -> Company:
        if name is not None:
            company.name = name.strip() or company.name
        if extras_patch:
            extras = dict(company.extras or {})
            extras.update(extras_patch)
            company.extras = extras
        self.session.add(company)
        self.session.flush()
        return company
