from __future__ import annotations

import json
import logging
import time
from collections.abc import Mapping
from typing import Any, TypeVar

import httpx
from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.services.privacy import strip_protected_disclosures
from app.schemas.gemini import (
    CandidateAnalysis,
    GeneratedJob,
    JobAnalysis,
    JobReview,
    MatchExplanation,
    PortfolioSourceAnalysis,
    ProjectAnalysis,
    ResumeAnalysis,
    SkillsExtraction,
    SourceAnalysis,
)

logger = logging.getLogger(__name__)

TModel = TypeVar("TModel", bound=BaseModel)

DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 3
RESUME_TEXT_LIMIT = 20_000
PROMPT_JSON_LIMIT = 15_000
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768
FALLBACK_MODELS = ("gemini-3.5-flash-lite", "gemini-3.6-flash")

OCR_INSTRUCTION = (
    "Extract all readable text from this resume. Return plain text only. Do not summarize."
)

RESUME_INSTRUCTION = """Extract a candidate profile from the resume text.
Return JSON only with this exact shape:
{
  "given_name": "",
  "middle_name": "",
  "family_name": "",
  "email": "",
  "phone": "",
  "address": "",
  "city": "",
  "country": "",
  "current_role": "",
  "summary": "",
  "experience": [{"title": "", "company_name": "", "start_date": "", "end_date": "", "description": ""}],
  "education": [{"school": "", "degree": "", "field_of_study": "", "start_date": "", "end_date": ""}],
  "skills": [{"skill": "", "years": null}],
  "technologies": [{"name": "", "years": null}],
  "projects": [{"name": "", "description": "", "url": ""}],
  "certifications": [{"name": "", "issuer": "", "issued_on": ""}],
  "achievements": [{"title": "", "description": "", "occurred_on": ""}]
}
Rules:
- Use ISO dates (YYYY-MM-DD) when possible. Use null for unknown years. Empty string when unknown.
- Infer skill and technology years from employment date ranges when the resume does not state years.
- Include skills implied by experience and project descriptions, not only an explicit skills list.
- Skills are capabilities. Technologies are tools, languages, or platforms.
- Normalize common names (React.js → React, TS → TypeScript, Postgres → PostgreSQL, Node.js → Node.js).
- Split city and country when an address contains both.
- Do not invent employers, schools, or projects that are not in the text.
"""

JOB_GENERATE_INSTRUCTION = """Turn this recruiter request into a structured job posting.
Return JSON only with this exact shape:
{
  "title": "",
  "description": "",
  "required_skills": [],
  "preferred_skills": [],
  "experience": {"years": 0, "text": ""},
  "education": "",
  "technologies": [],
  "responsibilities": [],
  "location": "",
  "salary_range": "",
  "employment_type": "",
  "seniority": "",
  "certifications": [],
  "openings": 1,
  "deadline": ""
}
Rules:
- Extract only facts the recruiter stated. Do not invent employers, company names, skills, or technologies.
- Put must-have skills in required_skills and nice-to-have skills in preferred_skills.
- Normalize common skill and technology names (React.js → React, TS → TypeScript, Postgres → PostgreSQL).
- For a range like 0-2 years, set experience.years to the upper bound and experience.text to the range.
- Default employment_type to "full_time" if unspecified.
- Leave deadline empty unless the recruiter gave a date (ISO YYYY-MM-DD).
- openings defaults to 1.
- Do not mark the job as published.
"""

_client: genai.Client | None = None
_client_fingerprint: tuple[str, str, str, str] | None = None


class GeminiError(RuntimeError):
    pass


class GeminiConfigError(GeminiError):
    pass


class GeminiQuotaError(GeminiError):
    def __init__(self, message: str = "Gemini quota exceeded. Switch to Manual, or try again later.") -> None:
        super().__init__(message)


class GeminiValidationError(GeminiError):
    def __init__(self) -> None:
        super().__init__("Could not read the model response. Try again in a moment.")


def _config_hint() -> str:
    if settings.environment.value in {"staging", "production"}:
        return "Set GOOGLE_CLOUD_PROJECT for Vertex AI."
    return "Set GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT."


def is_configured() -> bool:
    return settings.gemini_configured


def reset_client() -> None:
    global _client, _client_fingerprint
    _client = None
    _client_fingerprint = None


def analyze_resume(text: str) -> ResumeAnalysis:
    prompt = f"{RESUME_INSTRUCTION}\n{text[:RESUME_TEXT_LIMIT]}"
    return _generate(ResumeAnalysis, prompt)


def analyze_candidate(profile: Mapping[str, Any]) -> CandidateAnalysis:
    prompt = (
        "Analyze this candidate profile for a recruiter. "
        "Return a short summary, strengths, gaps, and one suggested next action.\n"
        f"{_dump_json(profile)}"
    )
    return _generate(CandidateAnalysis, prompt)


def analyze_job(job: Mapping[str, Any]) -> JobAnalysis:
    prompt = (
        "Normalize this job posting. Return normalized skills, seniority, and keywords.\n"
        f"Title: {job.get('title', '')}\n"
        f"Description: {job.get('description', '')}\n"
        f"Requirements: {_dump_json(job.get('requirements', {}))}"
    )
    return _generate(JobAnalysis, prompt)


def generate_job_from_prompt(prompt: str) -> GeneratedJob:
    snippet = (prompt or "").strip()[:RESUME_TEXT_LIMIT]
    if not snippet:
        raise GeminiValidationError()
    return _generate(GeneratedJob, f"{JOB_GENERATE_INSTRUCTION}\n{snippet}")


def review_job(job: Mapping[str, Any]) -> JobReview:
    prompt = (
        "Review this job posting for completeness and clarity. "
        "For each relevant field return status complete, missing, ambiguous, or invalid "
        "plus a short message. Also return an overall comment. Do not invent facts.\n"
        f"{_dump_json(job)}"
    )
    return _generate(JobReview, prompt)


def extract_skills(text: str) -> SkillsExtraction:
    prompt = (
        "Extract distinct skills and technologies from this text. "
        "Skills are capabilities; technologies are tools, languages, or platforms.\n"
        f"{text[:RESUME_TEXT_LIMIT]}"
    )
    return _generate(SkillsExtraction, prompt)


def analyze_project(project: Mapping[str, Any]) -> ProjectAnalysis:
    prompt = (
        "Summarize this project and infer skills demonstrated.\n"
        f"Name: {project.get('name', '')}\n"
        f"URL: {project.get('url', '')}\n"
        f"Description: {project.get('description', '')}"
    )
    return _generate(ProjectAnalysis, prompt)


def analyze_source(source: str, url: str, snippet: str) -> SourceAnalysis:
    prompt = (
        "Extract a candidate display name, current title, skills, technologies, location, "
        "and a short summary from this sourced profile text. "
        "Skills are capabilities. Technologies are tools, languages, or platforms. "
        "Normalize common names (React.js → React, TS → TypeScript, Postgres → PostgreSQL). "
        "Do not invent employers, skills, or locations that are not in the text.\n"
        f"Source: {source}\n"
        f"URL: {url}\n"
        f"Snippet: {snippet[:RESUME_TEXT_LIMIT]}"
    )
    return _generate(SourceAnalysis, prompt)


def analyze_portfolio_page(url: str, text: str) -> PortfolioSourceAnalysis:
    prompt = (
        "Extract professional evidence from this public portfolio or website text. "
        "Return a short summary, skills, technologies, location, projects, case studies, and achievements. "
        "Skills are capabilities. Technologies are tools, languages, or platforms. "
        "Normalize common names (React.js → React, TS → TypeScript, Postgres → PostgreSQL). "
        "Do not invent employers, projects, or locations that are not in the text.\n"
        f"URL: {url}\n"
        f"{text[:RESUME_TEXT_LIMIT]}"
    )
    return _generate(PortfolioSourceAnalysis, prompt)


def generate_match_explanation(
    job: Mapping[str, Any],
    candidate: Mapping[str, Any],
    scores: Mapping[str, Any],
) -> MatchExplanation:
    job = strip_protected_disclosures(dict(job))
    candidate = strip_protected_disclosures(dict(candidate))
    scores = strip_protected_disclosures(dict(scores))
    prompt = (
        "Write a recruiter-facing match narrative for this candidate and job. "
        "The Python engine already computed the numeric scores below. "
        "Use those numbers as facts. Do not recalculate, invent, contradict, or return a score. "
        "Do not invent employers, skills, or evidence that is not in the job or candidate JSON. "
        "Return explanation, evidence interpretation, strengths, weaknesses, and a recommendation.\n"
        f"Job: {_dump_json(job)}\n"
        f"Candidate: {_dump_json(candidate)}\n"
        f"Python scores: {_dump_json(scores)}"
    )
    return _generate(MatchExplanation, prompt)


def embed_text(text: str) -> list[float]:
    if not is_configured():
        raise GeminiConfigError(
            f"Gemini is not configured. {_config_hint()}"
        )
    snippet = (text or "").strip()[:RESUME_TEXT_LIMIT]
    if not snippet:
        return [0.0] * EMBEDDING_DIMENSIONS
    client = _get_client()
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=snippet,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSIONS),
    )
    values = _embedding_values(response)
    if len(values) < EMBEDDING_DIMENSIONS:
        values = values + [0.0] * (EMBEDDING_DIMENSIONS - len(values))
    return values[:EMBEDDING_DIMENSIONS]


def _model_candidates() -> list[str]:
    ordered: list[str] = []
    primary = settings.gemini_model or "gemini-3.5-flash"
    for name in (primary, *FALLBACK_MODELS):
        cleaned = str(name or "").strip()
        if cleaned and cleaned not in ordered:
            ordered.append(cleaned)
    return ordered


def _generate(
    model_cls: type[TModel],
    prompt: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    retries: int = MAX_RETRIES,
) -> TModel:
    models = _model_candidates()
    schema_name = model_cls.__name__
    last_error: BaseException | None = None
    saw_quota = False

    for model_index, model_name in enumerate(models):
        for attempt in range(1, retries + 1):
            logger.info(
                "gemini_request model=%s schema=%s attempt=%s prompt_chars=%s",
                model_name,
                schema_name,
                attempt,
                len(prompt),
            )
            try:
                client = _get_client()
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=model_cls,
                        http_options=types.HttpOptions(
                            timeout=int(timeout * 1000),
                            retry_options=types.HttpRetryOptions(attempts=1),
                        ),
                    ),
                )
                raw = (response.text or "").strip()
                try:
                    return model_cls.model_validate_json(raw)
                except ValidationError as exc:
                    raise GeminiValidationError() from exc
            except GeminiValidationError:
                raise
            except GeminiError:
                raise
            except Exception as exc:
                last_error = exc
                code = _error_code(exc)
                if code == 429:
                    saw_quota = True
                    logger.info(
                        "gemini_rate_limited model=%s schema=%s attempt=%s",
                        model_name,
                        schema_name,
                        attempt,
                    )
                    break
                if code == 404:
                    logger.info(
                        "gemini_model_unavailable model=%s schema=%s",
                        model_name,
                        schema_name,
                    )
                    break
                if not _is_retryable(exc) or attempt >= retries:
                    logger.exception(
                        "gemini_failed model=%s schema=%s attempts=%s",
                        model_name,
                        schema_name,
                        attempt,
                    )
                    raise GeminiError("Gemini request failed.") from exc
                delay = 2 ** (attempt - 1)
                logger.info(
                    "gemini_retry model=%s schema=%s attempt=%s delay_s=%s reason=%s",
                    model_name,
                    schema_name,
                    attempt,
                    delay,
                    type(exc).__name__,
                )
                time.sleep(delay)
        next_model = models[model_index + 1] if model_index + 1 < len(models) else None
        if next_model:
            logger.info("gemini_model_fallback from=%s to=%s", model_name, next_model)

    if saw_quota:
        raise GeminiQuotaError() from last_error
    raise GeminiError("Gemini request failed.") from last_error


def _get_client() -> genai.Client:
    global _client, _client_fingerprint
    fingerprint = _client_key()
    if _client is None or _client_fingerprint != fingerprint:
        _client = _build_client()
        _client_fingerprint = fingerprint
    return _client


def _client_key() -> tuple[str, str, str, str]:
    secret = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else ""
    return (
        str(settings.environment),
        secret,
        settings.google_cloud_project,
        settings.vertex_location,
    )


def extract_text_from_file(data: bytes, mime_type: str) -> str:
    if not is_configured():
        raise GeminiConfigError(f"Gemini is not configured. {_config_hint()}")
    client = _get_client()
    response = client.models.generate_content(
        model=settings.gemini_model or "gemini-3.5-flash",
        contents=[
            types.Part.from_bytes(data=data, mime_type=mime_type),
            OCR_INSTRUCTION,
        ],
    )
    text = (response.text or "").strip()
    if not text:
        raise GeminiError("Gemini request failed.")
    return text


def _build_client() -> genai.Client:
    if settings.use_vertex_ai:
        return genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.vertex_location,
        )
    if settings.gemini_api_key is not None:
        return genai.Client(api_key=settings.gemini_api_key.get_secret_value())
    raise GeminiConfigError(f"Gemini is not configured. {_config_hint()}")


def _dump_json(value: object) -> str:
    raw = json.dumps(value, default=str, ensure_ascii=False)
    if len(raw) > PROMPT_JSON_LIMIT:
        return raw[:PROMPT_JSON_LIMIT]
    return raw


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return True
    code = _error_code(exc)
    return isinstance(code, int) and code >= 500


def _error_code(exc: BaseException) -> int | None:
    for attr in ("code", "status_code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    return None


def _embedding_values(response: object) -> list[float]:
    embeddings = getattr(response, "embeddings", None)
    if embeddings:
        first = embeddings[0]
        values = getattr(first, "values", None)
        if values is not None:
            return [float(item) for item in values]
    embedding = getattr(response, "embedding", None)
    values = getattr(embedding, "values", None) if embedding is not None else None
    if values is not None:
        return [float(item) for item in values]
    raise GeminiError("Gemini embedding response was empty.")
