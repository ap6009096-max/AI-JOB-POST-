from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class CandidateGraphState(TypedDict, total=False):
    candidate_id: str
    current_node: str
    status: str
    errors: Annotated[list[dict[str, str]], operator.add]
    skipped: Annotated[list[dict[str, str]], operator.add]
    steps: Annotated[list[dict[str, str]], operator.add]
    resume_present: bool
    extraction_ok: bool
    validation_ok: bool
    embedding_ok: bool
    resume_text: str
    resume_content_type: str
    resume_bytes: bytes | None
    parse_result: dict[str, Any]
    github: dict[str, Any]
    linkedin: dict[str, Any]
    portfolio: dict[str, Any]
    other_sources: list[dict[str, Any]]
    merged: dict[str, Any]
    normalized: dict[str, Any]
    master: dict[str, Any]
    embedding: list[float]
