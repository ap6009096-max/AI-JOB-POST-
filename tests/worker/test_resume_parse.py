from app.resume_jobs import run_parse_resume
from app.tasks import TaskPayload


def test_worker_parse_resume_with_mocks(monkeypatch) -> None:
    calls: list[dict] = []

    monkeypatch.setattr("app.resume_jobs.get_bytes", lambda _key: b"%PDF-1.4")
    monkeypatch.setattr(
        "app.resume_jobs.parse_resume_bytes",
        lambda _data, _content_type: ("EXTRACTED", {"given_name": "Pat"}),
    )
    monkeypatch.setattr(
        "app.resume_jobs._callback",
        lambda candidate_id, **kwargs: calls.append({"candidate_id": candidate_id, **kwargs}),
    )

    result = run_parse_resume(
        TaskPayload(
            task_type="parse_resume",
            reference_id="cand-1",
            payload={
                "candidate_id": "11111111-1111-1111-1111-111111111111",
                "object_key": "candidates/x/resume/a.pdf",
                "content_type": "application/pdf",
            },
        )
    )
    assert result["status"] == "succeeded"
    assert calls[0]["status"] == "succeeded"
    assert calls[0]["text"] == "EXTRACTED"
    assert calls[0]["parse_result"]["given_name"] == "Pat"


def test_analyze_resume_text_uses_vertex_without_api_key(monkeypatch) -> None:
    import json
    from types import SimpleNamespace

    from app import resume_parse
    from app.config import Environment

    captured: dict = {}

    class FakeModels:
        def generate_content(self, **_kwargs):
            return SimpleNamespace(
                text=json.dumps(
                    {
                        "given_name": "Pat",
                        "family_name": "Kumar",
                        "skills": [{"skill": "Python", "years": 4}],
                    }
                )
            )

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.models = FakeModels()

    monkeypatch.setattr(resume_parse.settings, "environment", Environment.PRODUCTION)
    monkeypatch.setattr(resume_parse.settings, "gemini_api_key", None)
    monkeypatch.setattr(resume_parse.settings, "google_cloud_project", "imagi-ai-gpami")
    monkeypatch.setattr(resume_parse.settings, "google_cloud_location", "asia-south1")
    monkeypatch.setattr(resume_parse.settings, "gemini_model", "gemini-2.0-flash-001")

    import google.genai as genai

    monkeypatch.setattr(genai, "Client", FakeClient)

    result = resume_parse.analyze_resume_text("Pat Kumar\nPython engineer")
    assert captured.get("vertexai") is True
    assert captured.get("project") == "imagi-ai-gpami"
    assert result["given_name"] == "Pat"
    assert result["skills"][0]["skill"] == "Python"


def test_normalize_parse_result_coerces_string_skills() -> None:
    from app.resume_parse import normalize_parse_result

    parsed = normalize_parse_result({"skills": ["Python"], "technologies": ["FastAPI"]})
    assert parsed["skills"] == [{"skill": "Python"}]
    assert parsed["technologies"] == [{"name": "FastAPI"}]
