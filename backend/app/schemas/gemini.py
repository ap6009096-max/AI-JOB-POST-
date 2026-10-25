from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GeminiModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ResumeExperience(GeminiModel):
    title: str = ""
    company_name: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""


class ResumeEducation(GeminiModel):
    school: str = ""
    degree: str = ""
    field_of_study: str = ""
    start_date: str = ""
    end_date: str = ""


class ResumeSkill(GeminiModel):
    skill: str = ""
    years: float | None = None


class ResumeTechnology(GeminiModel):
    name: str = ""
    years: float | None = None


class ResumeProject(GeminiModel):
    name: str = ""
    description: str = ""
    url: str = ""


class ResumeCertification(GeminiModel):
    name: str = ""
    issuer: str = ""
    issued_on: str = ""


class ResumeAchievement(GeminiModel):
    title: str = ""
    description: str = ""
    occurred_on: str = ""


class ResumeAnalysis(GeminiModel):
    given_name: str
    middle_name: str
    family_name: str
    email: str
    phone: str
    address: str
    city: str
    country: str
    current_role: str
    summary: str
    experience: list[ResumeExperience]
    education: list[ResumeEducation]
    skills: list[ResumeSkill]
    technologies: list[ResumeTechnology]
    projects: list[ResumeProject]
    certifications: list[ResumeCertification]
    achievements: list[ResumeAchievement]


class CandidateAnalysis(GeminiModel):
    summary: str
    strengths: list[str]
    gaps: list[str]
    suggested_next_action: str


class JobAnalysis(GeminiModel):
    skills: list[str]
    seniority: str
    keywords: list[str]


class JobReviewNote(GeminiModel):
    field: str = ""
    status: str = "complete"
    message: str = ""


class JobReview(GeminiModel):
    overall: str = ""
    notes: list[JobReviewNote] = Field(default_factory=list)


class GeneratedJobExperience(GeminiModel):
    years: float = 0
    text: str = ""


class GeneratedJob(GeminiModel):
    title: str = ""
    description: str = ""
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience: GeneratedJobExperience = Field(default_factory=GeneratedJobExperience)
    education: str = ""
    technologies: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    location: str = ""
    salary_range: str = ""
    employment_type: str = ""
    seniority: str = ""
    certifications: list[str] = Field(default_factory=list)
    openings: int = 1
    deadline: str = ""


class SkillsExtraction(GeminiModel):
    skills: list[str]
    technologies: list[str]


class ProjectAnalysis(GeminiModel):
    summary: str
    skills: list[str]


class SourceAnalysis(GeminiModel):
    display_name: str = ""
    title: str = ""
    skills: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    location: str = ""
    summary: str = ""


class PortfolioProject(GeminiModel):
    name: str
    description: str
    url: str


class PortfolioCaseStudy(GeminiModel):
    title: str
    summary: str


class PortfolioAchievement(GeminiModel):
    title: str
    description: str


class PortfolioSourceAnalysis(GeminiModel):
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    location: str = ""
    projects: list[PortfolioProject] = Field(default_factory=list)
    case_studies: list[PortfolioCaseStudy] = Field(default_factory=list)
    achievements: list[PortfolioAchievement] = Field(default_factory=list)


class MatchExplanation(GeminiModel):
    explanation: str = ""
    evidence: str = ""
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommendation: str = ""
