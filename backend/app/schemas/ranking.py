from typing import Any, Literal

from pydantic import BaseModel, Field


class JobRequirements(BaseModel):
    skills: list[str] = Field(default_factory=list)
    experience_years: float = 0
    location: str = ""
    keywords: list[str] = Field(default_factory=list)


class JobExperience(BaseModel):
    years: float = 0
    text: str = ""


class JobCheckOut(BaseModel):
    field: str
    status: Literal["complete", "missing", "ambiguous", "invalid"]
    message: str = ""


class JobPipelineStepOut(BaseModel):
    node: str
    status: str = ""
    at: str = ""


class JobPipelineSkipOut(BaseModel):
    node: str
    reason: str = ""


class JobPipelineErrorOut(BaseModel):
    node: str
    code: str = ""
    message: str = ""


class JobPipelineOut(BaseModel):
    status: str = ""
    current_node: str = ""
    steps: list[JobPipelineStepOut] = Field(default_factory=list)
    errors: list[JobPipelineErrorOut] = Field(default_factory=list)
    skipped: list[JobPipelineSkipOut] = Field(default_factory=list)
    checks: list[JobCheckOut] = Field(default_factory=list)
    updated_at: str = ""
    review: str = ""


class JobOut(BaseModel):
    id: str
    company_id: str
    title: str
    description: str
    location: str = ""
    status: str = "draft"
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience: JobExperience = Field(default_factory=JobExperience)
    education: str = ""
    technologies: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    salary_range: str = ""
    employment_type: str = ""
    seniority: str = ""
    certifications: list[str] = Field(default_factory=list)
    openings: int = 1
    deadline: str = ""
    requirements: JobRequirements = Field(default_factory=JobRequirements)
    pipeline: JobPipelineOut | None = None
    embedding_id: str | None = None
    has_job_json: bool = False


class JobWriteFields(BaseModel):
    title: str | None = None
    description: str | None = None
    location: str | None = None
    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    experience: JobExperience | None = None
    education: str | None = None
    technologies: list[str] | None = None
    responsibilities: list[str] | None = None
    salary_range: str | None = None
    employment_type: str | None = None
    seniority: str | None = None
    certifications: list[str] | None = None
    openings: int | None = None
    deadline: str | None = None
    requirements: JobRequirements | None = None


class JobCreateIn(JobWriteFields):
    title: str = Field(min_length=1)
    status: Literal["draft", "open", "closed"] | None = None


class JobPatchIn(JobWriteFields):
    pass


class JobValidateOut(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)


class JobGenerateIn(BaseModel):
    prompt: str = Field(min_length=10)


class JobGenerateOut(BaseModel):
    job: JobOut
    valid: bool
    errors: list[str] = Field(default_factory=list)


class EmbeddingMetaOut(BaseModel):
    embedding_id: str
    model: str
    content_hash: str = ""
    cached: bool = False
    owner_type: str = ""
    owner_id: str = ""


class SimilarCandidateHit(BaseModel):
    embedding_id: str
    owner_id: str
    candidate_id: str = ""
    score: float


class MatchNarrative(BaseModel):
    explanation: str = ""
    evidence: str = ""
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommendation: str = ""


class RankedCandidate(BaseModel):
    rank: int
    candidate_id: str
    name: str
    title: str
    source: str | None = None
    identity_status: str | None = None
    location: str
    url: str = ""
    confidence: float | None = None
    score: float
    parts: dict[str, float]
    reasons: list[str]
    calculation_version: str = ""
    narrative: MatchNarrative | None = None
    matched_requirements: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)


class MatchResultOut(BaseModel):
    job_id: str
    candidate_id: str
    matching_run_id: str
    source_type: Literal["portal", "internet"]
    source: str
    overall_match_score: float
    skill_match_score: float = 0
    experience_match_score: float = 0
    project_match_score: float = 0
    education_match_score: float = 0
    technology_match_score: float = 0
    semantic_match_score: float = 0
    location_match_score: float = 0
    salary_match_score: float = 0
    matched_requirements: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    evidence: str = ""
    match_reasoning: str = ""
    recommendation: str = ""
    confidence_score: float = 0


class SourceSkipOut(BaseModel):
    source: str
    reason: str


class RankingRunOut(BaseModel):
    id: str
    job_id: str
    track: Literal["portal", "internet"]
    limit: int
    results: list[RankedCandidate]
    created_at: str
    skipped: list[SourceSkipOut] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class MatchingRunListOut(BaseModel):
    id: str
    job_id: str
    job_title: str = ""
    track: Literal["portal", "internet"]
    status: str
    limit: int = 0
    created_at: str


class CandidateOut(BaseModel):
    id: str
    track: Literal["portal", "internet"]
    profile: dict[str, Any]
