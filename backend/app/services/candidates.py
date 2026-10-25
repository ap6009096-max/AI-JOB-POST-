from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

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
from app.db.repositories import CandidateRepository, ProfileVersionRepository
from app.schemas.candidate import CANONICAL_LINK_SOURCES
from app.services.profile_completion import completion_flags, completion_percent, intelligence
from app.services.resume_parse import resume_public_view
from app.services.source_service import link_payload


def compose_full_name(personal: dict) -> str:
    parts = [
        str(personal.get("given_name") or "").strip(),
        str(personal.get("middle_name") or "").strip(),
        str(personal.get("family_name") or "").strip(),
    ]
    return " ".join(part for part in parts if part)


def _profile_ready(extras: dict, embedding_id: UUID | None) -> bool:
    pipeline = extras.get("candidate_pipeline") if isinstance(extras.get("candidate_pipeline"), dict) else {}
    status = str(pipeline.get("status") or "")
    return embedding_id is not None and status in {"completed", "completed_with_errors"}


def compose_location(city: str | None, country: str | None) -> str:
    city_value = (city or "").strip()
    country_value = (country or "").strip()
    if city_value and country_value:
        return f"{city_value}, {country_value}"
    return city_value or country_value


def _as_dict_list(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _professional_links(sources: list[CandidateSource]) -> dict:
    named = {key: "" for key in CANONICAL_LINK_SOURCES}
    other: list[dict] = []
    for row in sources:
        key = (row.source or "").strip().lower()
        if key in named:
            named[key] = row.url or ""
        else:
            other.append(link_payload(row))
    return {**named, "other": other}


class CandidateService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self._repo = CandidateRepository(session)

    def get(self, candidate_id: UUID) -> Candidate | None:
        return self._repo.get(candidate_id)

    def get_by_user_id(self, user_id: UUID) -> Candidate | None:
        return self._repo.get_by_user_id(user_id)

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Candidate]:
        return self._repo.list(limit=limit, offset=offset)

    def create(self, *, user_id: UUID | None = None, status: str = "active") -> Candidate:
        return self._repo.create(user_id=user_id, status=status)

    def create_profile(
        self,
        *,
        candidate_id: UUID,
        headline: str = "",
        summary: str = "",
        location: str = "",
        extras: dict | None = None,
    ) -> CandidateProfile:
        return self._repo.create_profile(
            candidate_id=candidate_id,
            headline=headline,
            summary=summary,
            location=location,
            extras=extras,
        )

    def ensure_for_user(self, user_id: UUID) -> Candidate:
        candidate = self._repo.get_by_user_id(user_id)
        if candidate is None:
            candidate = self._repo.create(user_id=user_id)
            self._repo.create_profile(candidate_id=candidate.id)
            candidate = self._repo.get_by_user_id(user_id)
        elif candidate.profile is None:
            self._repo.create_profile(candidate_id=candidate.id)
            candidate = self._repo.get_by_user_id(user_id)
        assert candidate is not None
        return candidate

    def _profile(self, candidate: Candidate) -> CandidateProfile:
        return candidate.profile or self._repo.create_profile(candidate_id=candidate.id)

    def update_profile(self, candidate: Candidate, **fields: str | None) -> CandidateProfile:
        return self._repo.update_profile(self._profile(candidate), **fields)

    def update_resume(self, candidate: Candidate, *, text: str = "", url: str = "") -> CandidateProfile:
        return self._repo.merge_extras(self._profile(candidate), "resume", {"text": text, "url": url})

    def update_resume_processing(self, candidate: Candidate, payload: dict) -> CandidateProfile:
        return self._repo.merge_extras(self._profile(candidate), "resume", payload)

    def update_preferences(self, candidate: Candidate, payload: dict) -> CandidateProfile:
        data = dict(payload)
        work_mode = data.get("work_mode")
        if work_mode:
            data["remote"] = work_mode == "remote"
        elif data.get("remote") is True:
            data["work_mode"] = "remote"
        elif data.get("remote") is False and data.get("work_mode") == "remote":
            data["work_mode"] = None
        return self._repo.merge_extras(self._profile(candidate), "preferences", data)

    def update_personal(self, user: User, candidate: Candidate, payload: dict) -> CandidateProfile:
        profile = self._repo.merge_extras(self._profile(candidate), "personal", payload)
        personal = dict((profile.extras or {}).get("personal") or {})
        full_name = compose_full_name(personal)
        if full_name:
            user.full_name = full_name
        if "city" in payload or "country" in payload:
            profile.location = compose_location(personal.get("city"), personal.get("country"))
        self.session.flush()
        return profile

    def update_settings(self, user: User, candidate: Candidate, *, full_name: str | None, status: str | None) -> None:
        if full_name is not None:
            user.full_name = full_name
        if status is not None:
            candidate.status = status
        self.session.flush()

    def upsert_professional_links(
        self,
        candidate: Candidate,
        *,
        linkedin: str = "",
        github: str = "",
        portfolio: str = "",
        website: str = "",
        other: list[dict] | None = None,
    ) -> None:
        named = {
            "linkedin": (linkedin or "").strip(),
            "github": (github or "").strip(),
            "portfolio": (portfolio or "").strip(),
            "website": (website or "").strip(),
        }
        existing = list(candidate.sources)
        by_key = {(row.source or "").strip().lower(): row for row in existing}
        for key, url in named.items():
            row = by_key.get(key)
            if url:
                if row is None:
                    self._repo.add_source(candidate_id=candidate.id, source=key, url=url)
                else:
                    row.url = url
            elif row is not None:
                self.session.delete(row)

        other_items = other or []
        keep_ids = {item["id"] for item in other_items if item.get("id")}
        for row in existing:
            key = (row.source or "").strip().lower()
            if key in CANONICAL_LINK_SOURCES:
                continue
            if row.id not in keep_ids:
                self.session.delete(row)

        for item in other_items:
            source = str(item.get("source") or "").strip() or "other"
            url = item.get("url")
            row_id = item.get("id")
            if row_id:
                owned = self._repo.get_owned(CandidateSource, row_id, candidate.id)
                if owned is None:
                    continue
                owned.source = source
                owned.url = url
            else:
                self._repo.add_source(candidate_id=candidate.id, source=source, url=url)
        self.session.flush()

    def graph_payload(self, candidate: Candidate, user: User) -> dict:
        profile = candidate.profile
        extras = dict(profile.extras or {}) if profile else {}
        personal = extras.get("personal") if isinstance(extras.get("personal"), dict) else {}
        flags = completion_flags(
            headline=profile.headline if profile else "",
            location=profile.location if profile else "",
            extras=extras,
            experience_count=len(candidate.experience),
            education_count=len(candidate.education),
            skill_count=len(candidate.skills),
            project_count=len(candidate.projects),
            certification_count=len(candidate.certifications),
            link_count=len(candidate.sources),
        )
        resume = extras.get("resume") if isinstance(extras.get("resume"), dict) else {}
        preferences = extras.get("preferences") if isinstance(extras.get("preferences"), dict) else {}
        return {
            "id": candidate.id,
            "full_name": user.full_name,
            "email": user.email,
            "status": candidate.status,
            "personal": {
                "given_name": personal.get("given_name") or "",
                "middle_name": personal.get("middle_name") or "",
                "family_name": personal.get("family_name") or "",
                "email": user.email,
                "phone": personal.get("phone") or "",
                "country": personal.get("country") or "",
                "city": personal.get("city") or "",
                "address": personal.get("address") or "",
            },
            "profile": {
                "headline": profile.headline if profile else "",
                "summary": profile.summary if profile else "",
                "location": profile.location if profile else "",
            },
            "resume": resume_public_view(resume),
            "preferences": {
                "open_to_work": preferences.get("open_to_work"),
                "remote": preferences.get("remote"),
                "work_mode": preferences.get("work_mode"),
                "salary_expectation": preferences.get("salary_expectation") or "",
                "employment_type": preferences.get("employment_type"),
                "locations": preferences.get("locations") or [],
                "desired_roles": preferences.get("desired_roles") or [],
                "notes": preferences.get("notes") or "",
            },
            "professional_links": _professional_links(list(candidate.sources)),
            "experience": candidate.experience,
            "education": candidate.education,
            "skills": candidate.skills,
            "technologies": _as_dict_list(extras.get("technologies")),
            "projects": candidate.projects,
            "certifications": candidate.certifications,
            "achievements": _as_dict_list(extras.get("achievements")),
            "links": [link_payload(row) for row in candidate.sources],
            "completion": {
                "percent": completion_percent(flags),
                "flags": flags,
            },
            "intelligence": intelligence(
                flags,
                skill_count=len(candidate.skills),
                experience_count=len(candidate.experience),
            ),
            "pipeline": extras.get("candidate_pipeline")
            if isinstance(extras.get("candidate_pipeline"), dict)
            else None,
            "master_candidate": extras.get("master_candidate")
            if isinstance(extras.get("master_candidate"), dict)
            else None,
            "embedding_id": profile.embedding_id if profile else None,
            "profile_ready": _profile_ready(extras, profile.embedding_id if profile else None),
            "profile_versions": [
                {
                    "id": row.id,
                    "version": row.version,
                    "source": row.source,
                    "change_summary": row.change_summary or {},
                    "created_at": row.created_at.isoformat() if row.created_at else "",
                }
                for row in ProfileVersionRepository(self.session).list(candidate.id)
            ],
        }

    def create_experience(self, candidate_id: UUID, **kwargs) -> CandidateExperience:
        return self._repo.add_experience(candidate_id=candidate_id, **kwargs)

    def create_education(self, candidate_id: UUID, **kwargs) -> CandidateEducation:
        return self._repo.add_education(candidate_id=candidate_id, **kwargs)

    def create_skill(self, candidate_id: UUID, **kwargs) -> CandidateSkill:
        return self._repo.add_skill(candidate_id=candidate_id, **kwargs)

    def create_project(self, candidate_id: UUID, **kwargs) -> CandidateProject:
        return self._repo.add_project(candidate_id=candidate_id, **kwargs)

    def create_certification(self, candidate_id: UUID, **kwargs) -> CandidateCertification:
        return self._repo.add_certification(candidate_id=candidate_id, **kwargs)

    def create_link(self, candidate_id: UUID, **kwargs) -> CandidateSource:
        return self._repo.add_source(candidate_id=candidate_id, **kwargs)

    def create_technology(self, candidate: Candidate, *, name: str, years: float | None = None) -> dict:
        return self._repo.add_extras_item(self._profile(candidate), "technologies", {"name": name, "years": years})

    def update_technology(self, candidate: Candidate, item_id: UUID, fields: dict) -> dict | None:
        return self._repo.update_extras_item(self._profile(candidate), "technologies", item_id, fields)

    def delete_technology(self, candidate: Candidate, item_id: UUID) -> bool:
        return self._repo.delete_extras_item(self._profile(candidate), "technologies", item_id)

    def create_achievement(
        self,
        candidate: Candidate,
        *,
        title: str,
        description: str = "",
        occurred_on: date | None = None,
    ) -> dict:
        return self._repo.add_extras_item(
            self._profile(candidate),
            "achievements",
            {
                "title": title,
                "description": description,
                "occurred_on": occurred_on.isoformat() if occurred_on else None,
            },
        )

    def update_achievement(self, candidate: Candidate, item_id: UUID, fields: dict) -> dict | None:
        payload = dict(fields)
        occurred_on = payload.get("occurred_on")
        if isinstance(occurred_on, date):
            payload["occurred_on"] = occurred_on.isoformat()
        return self._repo.update_extras_item(self._profile(candidate), "achievements", item_id, payload)

    def delete_achievement(self, candidate: Candidate, item_id: UUID) -> bool:
        return self._repo.delete_extras_item(self._profile(candidate), "achievements", item_id)

    def get_owned(self, model: type, row_id: UUID, candidate_id: UUID):
        return self._repo.get_owned(model, row_id, candidate_id)

    def delete_owned(self, model: type, row_id: UUID, candidate_id: UUID) -> bool:
        return self._repo.delete_owned(model, row_id, candidate_id)
