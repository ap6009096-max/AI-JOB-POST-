from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.core.config import Environment
from app.services import cloud_tasks, gemini_service, resume_storage
from app.services.gemini_service import GeminiConfigError


def test_local_api_key_preferred_over_vertex(monkeypatch) -> None:
    monkeypatch.setattr(gemini_service.settings, "environment", Environment.LOCAL)
    monkeypatch.setattr(gemini_service.settings, "gemini_api_key", SecretStr("local-test-key"))
    monkeypatch.setattr(gemini_service.settings, "google_cloud_project", "imagi-ai-gpami")
    captured: dict = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(gemini_service.genai, "Client", FakeClient)
    gemini_service.reset_client()
    gemini_service._build_client()
    assert captured.get("api_key") == "local-test-key"
    assert captured.get("vertexai") is not True


def test_vertex_preferred_when_project_set(monkeypatch) -> None:
    monkeypatch.setattr(gemini_service.settings, "environment", Environment.PRODUCTION)
    monkeypatch.setattr(gemini_service.settings, "gemini_api_key", SecretStr("ignored-key"))
    monkeypatch.setattr(gemini_service.settings, "google_cloud_project", "imagi-ai-gpami")
    monkeypatch.setattr(gemini_service.settings, "google_cloud_location", "asia-south1")
    captured: dict = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(gemini_service.genai, "Client", FakeClient)
    gemini_service.reset_client()
    gemini_service._build_client()
    assert captured.get("vertexai") is True
    assert captured.get("project") == "imagi-ai-gpami"
    assert "api_key" not in captured


def test_missing_credentials_mentions_vertex_in_production(monkeypatch) -> None:
    monkeypatch.setattr(gemini_service.settings, "environment", Environment.PRODUCTION)
    monkeypatch.setattr(gemini_service.settings, "gemini_api_key", None)
    monkeypatch.setattr(gemini_service.settings, "google_cloud_project", "")
    gemini_service.reset_client()
    with pytest.raises(GeminiConfigError, match="GOOGLE_CLOUD_PROJECT|Vertex|GEMINI"):
        gemini_service._build_client()


def test_gcs_put_get_bytes(monkeypatch) -> None:
    monkeypatch.setattr(resume_storage.settings, "environment", Environment.PRODUCTION)
    monkeypatch.setattr(resume_storage.settings, "gcs_bucket", "test-bucket")
    monkeypatch.setattr(resume_storage.settings, "google_cloud_project", "imagi-ai-gpami")
    monkeypatch.setattr(resume_storage.settings, "supabase_storage_bucket", "")

    store: dict[str, bytes] = {}

    class FakeBlob:
        def __init__(self, key: str):
            self.key = key

        def upload_from_string(self, data: bytes, content_type: str = "") -> None:
            store[self.key] = data

        def exists(self) -> bool:
            return self.key in store

        def download_as_bytes(self) -> bytes:
            return store[self.key]

    class FakeBucket:
        def blob(self, key: str) -> FakeBlob:
            return FakeBlob(key)

    monkeypatch.setattr(resume_storage, "_gcs_client_bucket", lambda: FakeBucket())
    resume_storage.put_bytes("candidates/x/resume.pdf", b"%PDF-1.4", "application/pdf")
    assert resume_storage.get_bytes("candidates/x/resume.pdf") == b"%PDF-1.4"


def test_cloud_tasks_enqueue_builds_oidc_task(monkeypatch) -> None:
    monkeypatch.setattr(cloud_tasks.settings, "environment", Environment.PRODUCTION)
    monkeypatch.setattr(cloud_tasks.settings, "google_cloud_project", "imagi-ai-gpami")
    monkeypatch.setattr(cloud_tasks.settings, "cloud_tasks_queue", "aether-hire-tasks")
    monkeypatch.setattr(cloud_tasks.settings, "worker_url", "https://worker.example.com")

    created: dict = {}

    class FakeClient:
        def queue_path(self, project, location, queue):
            return f"projects/{project}/locations/{location}/queues/{queue}"

        def create_task(self, request=None, **kwargs):
            created["request"] = request or kwargs
            return SimpleNamespace(name="tasks/1")

    class FakeTasksModule:
        class CloudTasksClient(FakeClient):
            pass

        class HttpMethod:
            POST = 1

    class FakeDuration:
        def __init__(self, seconds: int = 0):
            self.seconds = seconds

    import sys

    monkeypatch.setitem(sys.modules, "google.cloud.tasks_v2", FakeTasksModule())
    monkeypatch.setitem(
        sys.modules,
        "google.cloud",
        SimpleNamespace(tasks_v2=FakeTasksModule()),
    )
    monkeypatch.setitem(
        sys.modules,
        "google.protobuf.duration_pb2",
        SimpleNamespace(Duration=FakeDuration),
    )
    monkeypatch.setitem(
        sys.modules,
        "google.protobuf",
        SimpleNamespace(duration_pb2=SimpleNamespace(Duration=FakeDuration)),
    )

    # Force use_cloud_tasks true via project+queue+non-local
    assert cloud_tasks.settings.use_cloud_tasks is True

    ok = cloud_tasks.enqueue_parse_resume(
        uuid4(), object_key="k", content_type="application/pdf"
    )
    assert ok is True
    task = created["request"]["task"]
    assert task["http_request"]["url"] == "https://worker.example.com/tasks"
    assert "oidc_token" in task["http_request"]
    assert "aether-api@" in task["http_request"]["oidc_token"]["service_account_email"]
