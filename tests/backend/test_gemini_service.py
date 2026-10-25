from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.core.config import Environment, Settings
from app.services import gemini_service
from app.services.ai import AIGateway
from app.services.gemini_service import GeminiConfigError, GeminiQuotaError, GeminiValidationError


def _resume_json(**overrides: object) -> str:
    payload = {
        "given_name": "Pat",
        "middle_name": "",
        "family_name": "Kumar",
        "email": "pat@example.com",
        "phone": "",
        "address": "",
        "city": "Bengaluru",
        "country": "India",
        "current_role": "Engineer",
        "summary": "Builds recruiting tools.",
        "experience": [],
        "education": [],
        "skills": [{"skill": "Python", "years": 4}],
        "technologies": [{"name": "FastAPI", "years": 2}],
        "projects": [],
        "certifications": [],
        "achievements": [],
    }
    payload.update(overrides)
    return json.dumps(payload)


def _install_client(monkeypatch, generate_content) -> dict:
    captured: dict = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            return generate_content(**kwargs)

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.models = FakeModels()

    monkeypatch.setattr(gemini_service.genai, "Client", FakeClient)
    gemini_service.reset_client()
    return captured


@pytest.fixture(autouse=True)
def _reset_gemini_client():
    gemini_service.reset_client()
    yield
    gemini_service.reset_client()


@pytest.fixture
def local_api_key(monkeypatch):
    monkeypatch.setattr(gemini_service.settings, "environment", Environment.LOCAL)
    monkeypatch.setattr(gemini_service.settings, "gemini_api_key", SecretStr("test-gemini-key"))
    monkeypatch.setattr(gemini_service.settings, "google_cloud_project", "")
    gemini_service.reset_client()
    yield
    gemini_service.reset_client()


def test_extract_skills_parses_structured_output(monkeypatch, local_api_key) -> None:
    captured = _install_client(
        monkeypatch,
        lambda **_kwargs: SimpleNamespace(text='{"skills":["Python"],"technologies":["Django"]}'),
    )

    result = gemini_service.extract_skills("Used Python and Django")

    assert result.skills == ["Python"]
    assert result.technologies == ["Django"]
    assert captured["api_key"] == "test-gemini-key"
    assert captured.get("vertexai") is not True


def test_analyze_resume_returns_given_name(monkeypatch, local_api_key) -> None:
    _install_client(monkeypatch, lambda **_kwargs: SimpleNamespace(text=_resume_json()))

    result = gemini_service.analyze_resume("Pat Kumar\nPython engineer")

    assert result.given_name == "Pat"
    assert result.family_name == "Kumar"
    assert result.skills[0].skill == "Python"


def test_429_raises_quota_error_without_retry(monkeypatch, local_api_key) -> None:
    monkeypatch.setattr(gemini_service.settings, "gemini_model", "gemini-3.5-flash")
    calls = {"n": 0}
    slept: list[float] = []

    def generate_content(**_kwargs):
        calls["n"] += 1
        error = Exception("RESOURCE_EXHAUSTED")
        error.code = 429
        raise error

    _install_client(monkeypatch, generate_content)
    monkeypatch.setattr(gemini_service.time, "sleep", slept.append)

    with pytest.raises(GeminiQuotaError, match="quota exceeded"):
        gemini_service.extract_skills("Go services")

    assert calls["n"] == len(gemini_service._model_candidates())
    assert slept == []


def test_falls_back_to_3_5_flash_lite_after_primary_429(monkeypatch, local_api_key) -> None:
    monkeypatch.setattr(gemini_service.settings, "gemini_model", "gemini-3.5-flash")
    models: list[str] = []
    slept: list[float] = []

    def generate_content(**kwargs):
        model = str(kwargs.get("model") or "")
        models.append(model)
        if model == "gemini-3.5-flash":
            error = Exception("RESOURCE_EXHAUSTED")
            error.code = 429
            raise error
        return SimpleNamespace(text='{"skills":["Go"],"technologies":[]}')

    _install_client(monkeypatch, generate_content)
    monkeypatch.setattr(gemini_service.time, "sleep", slept.append)

    result = gemini_service.extract_skills("Go services")

    assert result.skills == ["Go"]
    assert models[:2] == ["gemini-3.5-flash", "gemini-3.5-flash-lite"]
    assert slept == []


def test_missing_credentials_raises(monkeypatch) -> None:
    monkeypatch.setattr(gemini_service.settings, "environment", Environment.LOCAL)
    monkeypatch.setattr(gemini_service.settings, "gemini_api_key", None)
    monkeypatch.setattr(gemini_service.settings, "google_cloud_project", "")
    gemini_service.reset_client()

    with pytest.raises(GeminiConfigError, match="GEMINI_API_KEY|GOOGLE_CLOUD_PROJECT|Vertex"):
        gemini_service.extract_skills("Python")


def test_project_prefers_vertex_over_api_key(monkeypatch) -> None:
    monkeypatch.setattr(gemini_service.settings, "environment", Environment.STAGING)
    monkeypatch.setattr(gemini_service.settings, "gemini_api_key", SecretStr("staging-gemini-key"))
    monkeypatch.setattr(gemini_service.settings, "google_cloud_project", "imagi-ai-gpami")
    monkeypatch.setattr(gemini_service.settings, "google_cloud_location", "asia-south1")
    captured = _install_client(
        monkeypatch,
        lambda **_kwargs: SimpleNamespace(text='{"skills":[],"technologies":[]}'),
    )

    gemini_service.extract_skills("ignored")

    assert captured.get("vertexai") is True
    assert captured.get("project") == "imagi-ai-gpami"
    assert "api_key" not in captured


def test_invalid_json_raises_user_safe_validation_error(monkeypatch, local_api_key) -> None:
    _install_client(monkeypatch, lambda **_kwargs: SimpleNamespace(text='{"skills":1}'))

    with pytest.raises(GeminiValidationError, match="Try again") as exc:
        gemini_service.extract_skills("Python")
    assert "skills" not in str(exc.value)
    assert "validation" not in str(exc.value).lower()


def test_ai_gateway_status_follows_credentials(monkeypatch) -> None:
    monkeypatch.setattr(gemini_service.settings, "gemini_api_key", None)
    monkeypatch.setattr(gemini_service.settings, "google_cloud_project", "")
    assert AIGateway().status() == "not_configured"

    monkeypatch.setattr(gemini_service.settings, "gemini_api_key", SecretStr("test-gemini-key"))
    assert AIGateway().status() == "configured"

    monkeypatch.setattr(gemini_service.settings, "gemini_api_key", None)
    monkeypatch.setattr(gemini_service.settings, "google_cloud_project", "proj")
    assert AIGateway().status() == "configured"


def test_blank_gemini_api_key_is_none() -> None:
    loaded = Settings(_env_file=None, gemini_api_key="")
    assert loaded.gemini_api_key is None


def test_request_logs_do_not_include_prompt_or_key(monkeypatch, local_api_key, caplog) -> None:
    _install_client(
        monkeypatch,
        lambda **_kwargs: SimpleNamespace(text='{"skills":["Python"],"technologies":[]}'),
    )
    caplog.set_level("INFO")

    gemini_service.extract_skills("SECRET_RESUME_TEXT")

    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "gemini_request" in messages
    assert "SECRET_RESUME_TEXT" not in messages
    assert "test-gemini-key" not in messages


def test_generate_job_from_prompt_parses_structured_output(monkeypatch, local_api_key) -> None:
    payload = {
        "title": "Python Developer",
        "description": "Build services in Patna.",
        "required_skills": ["Python", "Django", "SQL", "AWS"],
        "preferred_skills": [],
        "experience": {"years": 2, "text": "0-2 years"},
        "education": "",
        "technologies": ["Python", "Django"],
        "responsibilities": ["Write APIs"],
        "location": "Patna",
        "salary_range": "",
        "employment_type": "full_time",
        "seniority": "junior",
        "certifications": [],
        "openings": 1,
        "deadline": "",
    }
    _install_client(monkeypatch, lambda **_kwargs: SimpleNamespace(text=json.dumps(payload)))

    result = gemini_service.generate_job_from_prompt(
        "Create a Python Developer position in Patna for 0-2 years requiring Python, Django, SQL and basic AWS."
    )

    assert result.title == "Python Developer"
    assert result.location == "Patna"
    assert "Django" in result.required_skills
    assert result.experience.years == 2
    assert result.employment_type == "full_time"


def test_source_analysis_accepts_technologies_and_location(monkeypatch, local_api_key) -> None:
    payload = {
        "display_name": "Ada",
        "title": "Engineer",
        "skills": ["Python"],
        "technologies": ["FastAPI"],
        "location": "Bengaluru",
        "summary": "Builds APIs",
    }
    _install_client(monkeypatch, lambda **_kwargs: SimpleNamespace(text=json.dumps(payload)))

    result = gemini_service.analyze_source("github", "https://github.com/ada", "Ada builds FastAPI services in Bengaluru")

    assert result.technologies == ["FastAPI"]
    assert result.location == "Bengaluru"
    assert result.skills == ["Python"]
