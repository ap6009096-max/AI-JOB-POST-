from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import (
    Candidate,
    CandidateCertification,
    CandidateEducation,
    CandidateExperience,
    CandidateProfile,
    CandidateProject,
    CandidateSkill,
    CandidateSource,
    User,
)

_REGISTERED_LOADS = (
    selectinload(Candidate.profile),
    selectinload(Candidate.experience),
    selectinload(Candidate.education),
    selectinload(Candidate.skills),
    selectinload(Candidate.projects),
    selectinload(Candidate.certifications),
    selectinload(Candidate.sources),
    selectinload(Candidate.user),
)


class CandidateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, candidate_id: UUID) -> Candidate | None:
        return self.session.get(Candidate, candidate_id)

    def get_by_user_id(self, user_id: UUID) -> Candidate | None:
        return self.session.scalar(
            select(Candidate)
            .options(
                selectinload(Candidate.profile),
                selectinload(Candidate.experience),
                selectinload(Candidate.education),
                selectinload(Candidate.skills),
                selectinload(Candidate.projects),
                selectinload(Candidate.certifications),
                selectinload(Candidate.sources),
            )
            .where(Candidate.user_id == user_id)
        )

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Candidate]:
        return list(self.session.scalars(select(Candidate).offset(offset).limit(limit)))

    def list_registered(self) -> list[Candidate]:
        return list(
            self.session.scalars(
                select(Candidate)
                .join(User, Candidate.user_id == User.id)
                .options(*_REGISTERED_LOADS)
                .where(
                    Candidate.status == "active",
                    User.status == "active",
                    User.role == "candidate",
                )
            ).unique()
        )

    def get_registered(self, candidate_id: UUID) -> Candidate | None:
        return self.session.scalar(
            select(Candidate)
            .join(User, Candidate.user_id == User.id)
            .options(*_REGISTERED_LOADS)
            .where(
                Candidate.id == candidate_id,
                Candidate.status == "active",
                User.status == "active",
                User.role == "candidate",
            )
        )

    def create(self, *, user_id: UUID | None = None, status: str = "active") -> Candidate:
        candidate = Candidate(user_id=user_id, status=status)
        self.session.add(candidate)
        self.session.flush()
        return candidate

    def create_profile(
        self,
        *,
        candidate_id: UUID,
        headline: str = "",
        summary: str = "",
        location: str = "",
        extras: dict | None = None,
    ) -> CandidateProfile:
        profile = CandidateProfile(
            candidate_id=candidate_id,
            headline=headline,
            summary=summary,
            location=location,
            extras=extras or {},
        )
        self.session.add(profile)
        self.session.flush()
        return profile

    def update_profile(
        self,
        profile: CandidateProfile,
        *,
        headline: str | None = None,
        summary: str | None = None,
        location: str | None = None,
    ) -> CandidateProfile:
        if headline is not None:
            profile.headline = headline
        if summary is not None:
            profile.summary = summary
        if location is not None:
            profile.location = location
        self.session.flush()
        return profile

    def merge_extras(self, profile: CandidateProfile, key: str, value: dict) -> CandidateProfile:
        extras = dict(profile.extras or {})
        current = extras.get(key) if isinstance(extras.get(key), dict) else {}
        extras[key] = {**current, **value}
        profile.extras = extras
        flag_modified(profile, "extras")
        self.session.flush()
        return profile

    def _extras_items(self, profile: CandidateProfile, key: str) -> list[dict]:
        extras = dict(profile.extras or {})
        items = extras.get(key)
        return [dict(item) for item in items] if isinstance(items, list) else []

    def _save_extras_items(self, profile: CandidateProfile, key: str, items: list[dict]) -> CandidateProfile:
        extras = dict(profile.extras or {})
        extras[key] = items
        profile.extras = extras
        flag_modified(profile, "extras")
        self.session.flush()
        return profile

    def add_extras_item(self, profile: CandidateProfile, key: str, item: dict) -> dict:
        row = {"id": str(uuid4()), **item}
        items = self._extras_items(profile, key)
        items.append(row)
        self._save_extras_items(profile, key, items)
        return row

    def update_extras_item(self, profile: CandidateProfile, key: str, item_id: UUID, fields: dict) -> dict | None:
        target = str(item_id)
        items = self._extras_items(profile, key)
        updated: dict | None = None
        next_items: list[dict] = []
        for item in items:
            if str(item.get("id")) == target:
                updated = {**item, **fields, "id": target}
                next_items.append(updated)
            else:
                next_items.append(item)
        if updated is None:
            return None
        self._save_extras_items(profile, key, next_items)
        return updated

    def delete_extras_item(self, profile: CandidateProfile, key: str, item_id: UUID) -> bool:
        target = str(item_id)
        items = self._extras_items(profile, key)
        kept = [item for item in items if str(item.get("id")) != target]
        if len(kept) == len(items):
            return False
        self._save_extras_items(profile, key, kept)
        return True

    def add_skill(self, *, candidate_id: UUID, skill: str, years: float | None = None) -> CandidateSkill:
        row = CandidateSkill(candidate_id=candidate_id, skill=skill, years=years)
        self.session.add(row)
        self.session.flush()
        return row

    def add_experience(
        self,
        *,
        candidate_id: UUID,
        company_name: str,
        title: str,
        start_date: date | None = None,
        end_date: date | None = None,
        description: str = "",
    ) -> CandidateExperience:
        row = CandidateExperience(
            candidate_id=candidate_id,
            company_name=company_name,
            title=title,
            start_date=start_date,
            end_date=end_date,
            description=description,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def add_education(
        self,
        *,
        candidate_id: UUID,
        school: str,
        degree: str = "",
        field_of_study: str = "",
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> CandidateEducation:
        row = CandidateEducation(
            candidate_id=candidate_id,
            school=school,
            degree=degree,
            field_of_study=field_of_study,
            start_date=start_date,
            end_date=end_date,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def add_project(
        self,
        *,
        candidate_id: UUID,
        name: str,
        description: str = "",
        url: str | None = None,
    ) -> CandidateProject:
        row = CandidateProject(candidate_id=candidate_id, name=name, description=description, url=url)
        self.session.add(row)
        self.session.flush()
        return row

    def add_certification(
        self,
        *,
        candidate_id: UUID,
        name: str,
        issuer: str = "",
        issued_on: date | None = None,
    ) -> CandidateCertification:
        row = CandidateCertification(
            candidate_id=candidate_id,
            name=name,
            issuer=issuer,
            issued_on=issued_on,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def add_source(
        self,
        *,
        candidate_id: UUID,
        source: str,
        url: str | None = None,
    ) -> CandidateSource:
        row = CandidateSource(candidate_id=candidate_id, source=source, url=url)
        self.session.add(row)
        self.session.flush()
        return row

    def get_source_by_key(self, candidate_id: UUID, source: str) -> CandidateSource | None:
        return self.session.scalar(
            select(CandidateSource).where(
                CandidateSource.candidate_id == candidate_id,
                CandidateSource.source == source,
            )
        )

    def get_owned(self, model: type, row_id: UUID, candidate_id: UUID):
        row = self.session.get(model, row_id)
        if row is None or getattr(row, "candidate_id", None) != candidate_id:
            return None
        return row

    def delete_owned(self, model: type, row_id: UUID, candidate_id: UUID) -> bool:
        row = self.get_owned(model, row_id, candidate_id)
        if row is None:
            return False
        self.session.delete(row)
        self.session.flush()
        return True
