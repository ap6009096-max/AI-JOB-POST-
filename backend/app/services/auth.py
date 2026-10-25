from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import CompanyUser, User
from app.db.repositories.candidates import CandidateRepository
from app.db.repositories.companies import CompanyRepository
from app.db.repositories.users import UserRepository

INTENT_ROLES = {
    "candidate": "candidate",
    "recruiter": "recruiter",
    "company": "company_admin",
}


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.companies = CompanyRepository(session)
        self.candidates = CandidateRepository(session)

    def bootstrap(
        self,
        *,
        auth_user_id: UUID,
        email: str,
        intent: str,
        full_name: str = "",
        company_name: str | None = None,
    ) -> User:
        if intent not in INTENT_ROLES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid intent")

        user = self.users.get_by_auth_user_id(auth_user_id)
        if user is None:
            user = self.users.create(
                email=(email or f"{auth_user_id}@users.local").strip().lower(),
                full_name=full_name,
                auth_user_id=auth_user_id,
            )

        if user.role is not None:
            self._sync_app_metadata(auth_user_id, user.role)
            return user

        role = INTENT_ROLES[intent]
        user.role = role
        if full_name and not user.full_name:
            user.full_name = full_name

        if role == "candidate":
            candidate = self.candidates.create(user_id=user.id)
            self.candidates.create_profile(candidate_id=candidate.id)
        elif role == "company_admin":
            name = (company_name or "").strip() or f"{user.full_name or 'Company'}'s company"
            company = self.companies.create(name=name)
            self.companies.add_member(company_id=company.id, user_id=user.id, role="owner")

        self.session.commit()
        self.session.refresh(user)
        self._sync_app_metadata(auth_user_id, role)
        return user

    def add_company_member(self, *, admin: User, email: str, company_id: UUID) -> CompanyUser:
        member = self.users.get_by_email(email.strip().lower())
        if member is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if member.role == "candidate":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot add a candidate to a company",
            )
        if member.role is None:
            member.role = "recruiter"
        existing = [
            row
            for row in self.companies.list_members(company_id)
            if row.user_id == member.id
        ]
        if existing:
            self.session.commit()
            return existing[0]
        membership = self.companies.add_member(company_id=company_id, user_id=member.id, role="recruiter")
        self.session.commit()
        self.session.refresh(membership)
        if member.auth_user_id is not None:
            self._sync_app_metadata(member.auth_user_id, member.role or "recruiter")
        return membership

    def _sync_app_metadata(self, auth_user_id: UUID, role: str) -> None:
        if settings.supabase_service_role_key is None or not settings.supabase_url:
            return
        secret = settings.supabase_service_role_key.get_secret_value()
        url = f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users/{auth_user_id}"
        try:
            response = httpx.put(
                url,
                headers={
                    "Authorization": f"Bearer {secret}",
                    "apikey": secret,
                    "Content-Type": "application/json",
                },
                json={"app_metadata": {"role": role}},
                timeout=10,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            # DB role is canonical; JWT app_metadata is best-effort until refresh.
            return
