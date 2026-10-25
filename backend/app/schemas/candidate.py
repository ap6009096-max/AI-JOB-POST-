from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.gemini import (
    ResumeAchievement,
    ResumeCertification,
    ResumeEducation,
    ResumeExperience,
    ResumeProject,
    ResumeSkill,
    ResumeTechnology,
)


CANONICAL_LINK_SOURCES = ("linkedin", "github", "portfolio", "website")
WORK_MODES = ("remote", "hybrid", "onsite")
EMPLOYMENT_TYPES = ("full_time", "part_time", "contract", "internship", "freelance")


def coerce_named_items(value: object, name_key: str) -> list[dict]:
    if not isinstance(value, list):
        return []
    items: list[dict] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            items.append({name_key: item.strip()})
        elif isinstance(item, dict):
            items.append(item)
    return items


def coerce_legacy_named_lists(data: object) -> object:
    if not isinstance(data, dict):
        return data
    payload = dict(data)
    payload["skills"] = coerce_named_items(payload.get("skills"), "skill")
    payload["technologies"] = coerce_named_items(payload.get("technologies"), "name")
    return payload


class ResumeProcessingOut(BaseModel):
    status: str = ""
    error: str = ""
    started_at: str = ""
    finished_at: str = ""
    applied_at: str = ""


class ResumeParseResultOut(BaseModel):
    given_name: str = ""
    middle_name: str = ""
    family_name: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""
    city: str = ""
    country: str = ""
    current_role: str = ""
    summary: str = ""
    experience: list[ResumeExperience] = Field(default_factory=list)
    education: list[ResumeEducation] = Field(default_factory=list)
    skills: list[ResumeSkill] = Field(default_factory=list)
    technologies: list[ResumeTechnology] = Field(default_factory=list)
    projects: list[ResumeProject] = Field(default_factory=list)
    certifications: list[ResumeCertification] = Field(default_factory=list)
    achievements: list[ResumeAchievement] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def coerce_legacy_lists(cls, data: object) -> object:
        return coerce_legacy_named_lists(data)


class ResumeOut(BaseModel):
    text: str = ""
    url: str = ""
    filename: str = ""
    content_type: str = ""
    size_bytes: int = 0
    processing: ResumeProcessingOut = Field(default_factory=ResumeProcessingOut)
    parse_result: ResumeParseResultOut | None = None


class PreferencesOut(BaseModel):
    open_to_work: bool | None = None
    remote: bool | None = None
    work_mode: str | None = None
    salary_expectation: str = ""
    employment_type: str | None = None
    locations: list[str] = Field(default_factory=list)
    desired_roles: list[str] = Field(default_factory=list)
    notes: str = ""


class PersonalOut(BaseModel):
    given_name: str = ""
    middle_name: str = ""
    family_name: str = ""
    email: str = ""
    phone: str = ""
    country: str = ""
    city: str = ""
    address: str = ""


class ProfileCoreOut(BaseModel):
    headline: str = ""
    summary: str = ""
    location: str = ""


class CompletionOut(BaseModel):
    percent: int
    flags: dict[str, bool]


class IntelligenceOut(BaseModel):
    missing_sections: list[str]
    next_action: str
    skill_count: int
    experience_count: int


class PipelineStepOut(BaseModel):
    node: str
    status: str = ""
    at: str = ""


class PipelineSkipOut(BaseModel):
    node: str
    reason: str = ""


class PipelineErrorOut(BaseModel):
    node: str
    code: str = ""
    message: str = ""


class PipelineOut(BaseModel):
    status: str = ""
    current_node: str = ""
    steps: list[PipelineStepOut] = Field(default_factory=list)
    errors: list[PipelineErrorOut] = Field(default_factory=list)
    skipped: list[PipelineSkipOut] = Field(default_factory=list)
    updated_at: str = ""


class MasterCandidate(BaseModel):
    given_name: str = ""
    middle_name: str = ""
    family_name: str = ""
    current_role: str = ""
    summary: str = ""
    city: str = ""
    country: str = ""
    skills: list[ResumeSkill] = Field(default_factory=list)
    technologies: list[ResumeTechnology] = Field(default_factory=list)
    experience: list[ResumeExperience] = Field(default_factory=list)
    education: list[ResumeEducation] = Field(default_factory=list)
    projects: list[ResumeProject] = Field(default_factory=list)
    certifications: list[ResumeCertification] = Field(default_factory=list)
    achievements: list[ResumeAchievement] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)
    provenance: dict[str, list[str]] = Field(default_factory=dict)
    timestamp: str = ""

    @model_validator(mode="before")
    @classmethod
    def coerce_legacy_lists(cls, data: object) -> object:
        return coerce_legacy_named_lists(data)


class ProfileVersionOut(BaseModel):
    id: UUID
    version: int
    source: str = ""
    change_summary: dict = Field(default_factory=dict)
    created_at: str = ""


class ProfileVersionDetailOut(ProfileVersionOut):
    snapshot: dict = Field(default_factory=dict)


class ExperienceOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    company_name: str
    title: str
    start_date: date | None = None
    end_date: date | None = None
    description: str = ""


class EducationOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    school: str
    degree: str = ""
    field_of_study: str = ""
    start_date: date | None = None
    end_date: date | None = None


class SkillOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    skill: str
    years: float | None = None


class ProjectOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    description: str = ""
    url: str | None = None


class CertificationOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    issuer: str = ""
    issued_on: date | None = None


class SourceAnalysisOut(BaseModel):
    url: str = ""
    analyzed_at: str = ""
    provenance: str = ""
    fetch_status: str = ""
    skip_reason: str = ""
    evidence: dict = Field(default_factory=dict)
    analysis: dict = Field(default_factory=dict)


class LinkOut(BaseModel):
    id: UUID
    source: str
    url: str | None = None
    created_at: str = ""
    updated_at: str = ""
    analysis: SourceAnalysisOut | None = None


class TechnologyOut(BaseModel):
    id: UUID
    name: str
    years: float | None = None


class AchievementOut(BaseModel):
    id: UUID
    title: str
    description: str = ""
    occurred_on: date | None = None


class ProfessionalLinksOut(BaseModel):
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    website: str = ""
    other: list[LinkOut] = Field(default_factory=list)


class CandidateGraphOut(BaseModel):
    id: UUID
    full_name: str
    email: str
    status: str
    personal: PersonalOut
    profile: ProfileCoreOut
    resume: ResumeOut
    preferences: PreferencesOut
    professional_links: ProfessionalLinksOut
    experience: list[ExperienceOut]
    education: list[EducationOut]
    skills: list[SkillOut]
    technologies: list[TechnologyOut]
    projects: list[ProjectOut]
    certifications: list[CertificationOut]
    achievements: list[AchievementOut]
    links: list[LinkOut]
    completion: CompletionOut
    intelligence: IntelligenceOut
    pipeline: PipelineOut | None = None
    master_candidate: dict | None = None
    embedding_id: UUID | None = None
    profile_ready: bool = False
    profile_versions: list[ProfileVersionOut] = Field(default_factory=list)


class ProfilePatch(BaseModel):
    headline: str | None = None
    summary: str | None = None
    location: str | None = None


class PersonalPatch(BaseModel):
    given_name: str | None = None
    middle_name: str | None = None
    family_name: str | None = None
    phone: str | None = None
    country: str | None = None
    city: str | None = None
    address: str | None = None


class ResumePut(BaseModel):
    text: str = ""
    url: str = ""


class ResumeParseApplyIn(ResumeParseResultOut):
    pass


class ResumeCompleteIn(BaseModel):
    candidate_id: UUID
    status: str = Field(pattern="^(succeeded|failed)$")
    text: str = ""
    parse_result: dict | None = None
    error: str = ""


class PreferencesPut(BaseModel):
    open_to_work: bool | None = None
    remote: bool | None = None
    work_mode: str | None = Field(default=None, pattern="^(remote|hybrid|onsite)$")
    salary_expectation: str | None = None
    employment_type: str | None = Field(
        default=None, pattern="^(full_time|part_time|contract|internship|freelance)$"
    )
    locations: list[str] | None = None
    desired_roles: list[str] | None = None
    notes: str | None = None


class SettingsPatch(BaseModel):
    full_name: str | None = None
    status: str | None = Field(default=None, pattern="^(active|hidden)$")


class OtherLinkIn(BaseModel):
    id: UUID | None = None
    source: str
    url: str | None = None


class ProfessionalLinksPut(BaseModel):
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    website: str = ""
    other: list[OtherLinkIn] = Field(default_factory=list)


class ExperienceIn(BaseModel):
    company_name: str
    title: str
    start_date: date | None = None
    end_date: date | None = None
    description: str = ""


class ExperiencePatch(BaseModel):
    company_name: str | None = None
    title: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None


class EducationIn(BaseModel):
    school: str
    degree: str = ""
    field_of_study: str = ""
    start_date: date | None = None
    end_date: date | None = None


class EducationPatch(BaseModel):
    school: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class SkillIn(BaseModel):
    skill: str
    years: float | None = None


class SkillPatch(BaseModel):
    skill: str | None = None
    years: float | None = None


class ProjectIn(BaseModel):
    name: str
    description: str = ""
    url: str | None = None


class ProjectPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    url: str | None = None


class CertificationIn(BaseModel):
    name: str
    issuer: str = ""
    issued_on: date | None = None


class CertificationPatch(BaseModel):
    name: str | None = None
    issuer: str | None = None
    issued_on: date | None = None


class LinkIn(BaseModel):
    source: str
    url: str | None = None


class LinkPatch(BaseModel):
    source: str | None = None
    url: str | None = None


class TechnologyIn(BaseModel):
    name: str
    years: float | None = None


class TechnologyPatch(BaseModel):
    name: str | None = None
    years: float | None = None


class AchievementIn(BaseModel):
    title: str
    description: str = ""
    occurred_on: date | None = None


class AchievementPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    occurred_on: date | None = None


class JobRecommendationOut(BaseModel):
    rank: int
    job_id: UUID
    title: str
    location: str = ""
    company_id: UUID
    score: float
    parts: dict[str, float] = Field(default_factory=dict)
    matched_requirements: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    calculation_version: str = ""
