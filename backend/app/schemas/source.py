from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class SourceAgentResult(BaseModel):
    url: str = ""
    analyzed_at: str = ""
    provenance: str = ""
    fetch_status: str = ""
    skip_reason: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    analysis: dict[str, Any] = Field(default_factory=dict)

    def to_extras(self) -> dict[str, Any]:
        return self.model_dump()


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class RedditEvidence(BaseModel):
    source: str = "Reddit"
    source_url: str = ""
    profile_identifier: str = ""
    professional_evidence: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    relevant_experience: list[str] = Field(default_factory=list)
    timestamp: str = ""
