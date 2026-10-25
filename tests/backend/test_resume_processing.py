from contextlib import contextmanager
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import Principal, get_current_user
from app.db.models import User
from app.db.repositories.users import UserRepository
from app.db.session import get_db
from app.main import app
from app.services.resume_files import MAX_RESUME_BYTES, ResumeFileError, validate_resume_file

client = TestClient(app)

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@contextmanager
def acting_as(user: User, db_session):
    def override_user() -> Principal:
        return Principal(user=user, claims={}, memberships=[])

    def override_db():
        yield db_session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def _user(db_session, *, role: str) -> User:
    return UserRepository(db_session).create(
        email=f"{role}-{uuid4().hex[:8]}@example.com",
        full_name="Pat Candidate",
        role=role,
    )


def test_validate_rejects_oversize_and_bad_type() -> None:
    try:
        validate_resume_file(data=b"%PDF" + b"x" * MAX_RESUME_BYTES, declared_type="application/pdf", filename="big.pdf")
        raise AssertionError("expected size error")
    except ResumeFileError as exc:
        assert "5 MB" in str(exc)
    try:
        validate_resume_file(data=b"not-a-resume", declared_type="text/plain", filename="note.txt")
        raise AssertionError("expected type error")
    except ResumeFileError as exc:
        assert "PDF" in str(exc)


def test_recruiter_cannot_upload_resume(db_session) -> None:
    recruiter = _user(db_session, role="recruiter")
    with acting_as(recruiter, db_session):
        response = client.post(
            "/v1/me/candidate/resume/upload",
            files={"file": ("cv.pdf", PDF, "application/pdf")},
        )
    assert response.status_code == 403


def test_candidate_upload_processes_with_mocks(db_session, monkeypatch, tmp_path) -> None:
    from app.core import config
    from app.services import resume_jobs, resume_storage

    monkeypatch.setattr(config.settings, "resume_local_dir", str(tmp_path))
    monkeypatch.setattr(config.settings, "supabase_storage_bucket", "")
    monkeypatch.setattr(resume_jobs, "_enqueue_worker", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        resume_jobs,
        "parse_resume_bytes",
        lambda _data, _content_type: (
            "EXTRACTED TEXT",
            {"given_name": "Pat", "family_name": "Kumar", "skills": [{"skill": "Python", "years": 4}]},
        ),
    )
    monkeypatch.setattr(resume_storage, "local_root", lambda: tmp_path)

    candidate = _user(db_session, role="candidate")
    with acting_as(candidate, db_session):
        uploaded = client.post(
            "/v1/me/candidate/resume/upload",
            files={"file": ("cv.pdf", PDF, "application/pdf")},
        )
        assert uploaded.status_code == 200
        body = uploaded.json()["resume"]
        assert body["processing"]["status"] == "succeeded"
        assert body["text"] == "EXTRACTED TEXT"
        assert body["parse_result"]["given_name"] == "Pat"
        assert "object_key" not in body
        graph = uploaded.json()
        assert graph["personal"]["given_name"] == "Pat"
        assert any(row["skill"] == "Python" for row in graph["skills"])
        assert graph["resume"]["processing"]["applied_at"]

        applied = client.post("/v1/me/candidate/resume/apply")
        assert applied.status_code == 400
        assert "already applied" in applied.json()["detail"]


def test_upload_auto_applies_experience_and_keeps_account_email(db_session, monkeypatch, tmp_path) -> None:
    from app.core import config
    from app.services import resume_jobs, resume_storage

    monkeypatch.setattr(config.settings, "resume_local_dir", str(tmp_path))
    monkeypatch.setattr(config.settings, "supabase_storage_bucket", "")
    monkeypatch.setattr(resume_jobs, "_enqueue_worker", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        resume_jobs,
        "parse_resume_bytes",
        lambda _data, _content_type: (
            "EXTRACTED TEXT",
            {
                "given_name": "Pat",
                "family_name": "Kumar",
                "email": "from-resume@example.com",
                "experience": [
                    {
                        "title": "Engineer",
                        "company_name": "Acme",
                        "start_date": "",
                        "end_date": "",
                        "description": "Built APIs",
                    }
                ],
                "skills": [{"skill": "Python", "years": 4}],
            },
        ),
    )
    monkeypatch.setattr(resume_storage, "local_root", lambda: tmp_path)

    candidate = _user(db_session, role="candidate")
    account_email = candidate.email
    with acting_as(candidate, db_session):
        uploaded = client.post(
            "/v1/me/candidate/resume/upload",
            files={"file": ("cv.pdf", PDF, "application/pdf")},
        )
        assert uploaded.status_code == 200
        graph = uploaded.json()
        assert graph["personal"]["given_name"] == "Pat"
        assert graph["email"] == account_email
        assert graph["personal"]["email"] == account_email
        assert any(row["company_name"] == "Acme" for row in graph["experience"])
        assert [row["skill"] for row in graph["skills"]] == ["Python"]
        assert graph["resume"]["processing"]["applied_at"]

        again = client.post("/v1/me/candidate/resume/apply")
        assert again.status_code == 400
        assert "already applied" in again.json()["detail"]


def test_upload_rejects_oversize(db_session) -> None:
    candidate = _user(db_session, role="candidate")
    huge = b"%PDF-1.4\n" + b"x" * MAX_RESUME_BYTES
    with acting_as(candidate, db_session):
        response = client.post(
            "/v1/me/candidate/resume/upload",
            files={"file": ("cv.pdf", huge, "application/pdf")},
        )
    assert response.status_code == 400


def test_local_upload_writes_disk_when_storage_bucket_set(monkeypatch, tmp_path) -> None:
    from app.core.config import Environment
    from app.services import resume_storage

    monkeypatch.setattr(resume_storage.settings, "environment", Environment.LOCAL)
    monkeypatch.setattr(resume_storage.settings, "supabase_storage_bucket", "resumes")
    monkeypatch.setattr(resume_storage.settings, "resume_local_dir", str(tmp_path))

    resume_storage.put_bytes("candidates/x/resume.pdf", PDF, "application/pdf")

    stored = tmp_path / "candidates" / "x" / "resume.pdf"
    assert stored.read_bytes() == PDF
    assert resume_storage.get_bytes("candidates/x/resume.pdf") == PDF


def test_local_extract_text_skips_document_ai(monkeypatch) -> None:
    from app.core.config import Environment
    from app.services import resume_parse
    from app.services.resume_files import MIME_PDF

    monkeypatch.setattr(resume_parse.settings, "environment", Environment.LOCAL)
    monkeypatch.setattr(resume_parse.settings, "document_ai_processor_id", "processor-id")
    monkeypatch.setattr(
        resume_parse,
        "_extract_document_ai",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Document AI must not run locally")),
    )
    monkeypatch.setattr(
        resume_parse,
        "_extract_pdf_local",
        lambda _data, **_kwargs: "LOCAL PDF TEXT",
    )

    assert resume_parse.extract_text(PDF, MIME_PDF) == "LOCAL PDF TEXT"


def test_empty_parse_does_not_auto_apply(db_session, monkeypatch, tmp_path) -> None:
    from app.core import config
    from app.services import resume_jobs, resume_storage

    monkeypatch.setattr(config.settings, "resume_local_dir", str(tmp_path))
    monkeypatch.setattr(config.settings, "supabase_storage_bucket", "")
    monkeypatch.setattr(resume_jobs, "_enqueue_worker", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        resume_jobs,
        "parse_resume_bytes",
        lambda _data, _content_type: ("EXTRACTED TEXT", {}),
    )
    monkeypatch.setattr(resume_storage, "local_root", lambda: tmp_path)

    candidate = _user(db_session, role="candidate")
    with acting_as(candidate, db_session):
        uploaded = client.post(
            "/v1/me/candidate/resume/upload",
            files={"file": ("cv.pdf", PDF, "application/pdf")},
        )
    assert uploaded.status_code == 200
    graph = uploaded.json()
    assert graph["resume"]["processing"]["status"] == "succeeded"
    assert not graph["resume"]["processing"]["applied_at"]
    assert graph["personal"]["given_name"] == ""
    assert graph["skills"] == []


def test_put_resume_parses_pasted_text(db_session, monkeypatch) -> None:
    from app.services import resume_jobs

    monkeypatch.setattr(
        resume_jobs,
        "analyze_resume_text",
        lambda _text: {
            "given_name": "Pat",
            "family_name": "Kumar",
            "skills": [{"skill": "Python", "years": 4}],
        },
    )

    candidate = _user(db_session, role="candidate")
    pasted = "Pat Kumar is a Python engineer with four years of backend experience."
    with acting_as(candidate, db_session):
        saved = client.put("/v1/me/candidate/resume", json={"text": pasted, "url": ""})
    assert saved.status_code == 200
    graph = saved.json()
    assert graph["resume"]["text"] == pasted
    assert graph["personal"]["given_name"] == "Pat"
    assert any(row["skill"] == "Python" for row in graph["skills"])
    assert graph["resume"]["processing"]["applied_at"]


def test_put_resume_keeps_text_when_gemini_fails(db_session, monkeypatch) -> None:
    from app.services import resume_jobs
    from app.services.resume_parse import ResumeParseError

    monkeypatch.setattr(
        resume_jobs,
        "analyze_resume_text",
        lambda _text: (_ for _ in ()).throw(ResumeParseError("Could not analyze this resume.", stage="gemini")),
    )

    candidate = _user(db_session, role="candidate")
    pasted = "Pat Kumar is a Python engineer with four years of backend experience."
    with acting_as(candidate, db_session):
        saved = client.put("/v1/me/candidate/resume", json={"text": pasted, "url": ""})
    assert saved.status_code == 200
    graph = saved.json()
    assert graph["resume"]["text"] == pasted
    assert graph["personal"]["given_name"] == ""
    assert not graph["resume"]["processing"]["applied_at"]


def test_missing_pypdf_is_resume_parse_error(monkeypatch) -> None:
    import builtins

    from app.services import resume_parse

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pypdf" or name.startswith("pypdf."):
            raise ImportError("No module named 'pypdf'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    try:
        resume_parse._extract_pdf_local(PDF)
        raise AssertionError("expected parse error")
    except resume_parse.ResumeParseError as exc:
        assert exc.stage == "ocr"


def test_empty_pdf_falls_back_to_gemini_ocr(monkeypatch) -> None:
    from app.services import resume_parse
    from app.services.resume_files import MIME_PDF

    monkeypatch.setattr(resume_parse, "_use_document_ai", lambda: False)
    monkeypatch.setattr(resume_parse, "_extract_pdf_local", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(resume_parse, "_extract_gemini_ocr", lambda *_args, **_kwargs: "SCANNED TEXT")

    assert resume_parse.extract_text(PDF, MIME_PDF) == "SCANNED TEXT"


def test_image_extract_uses_gemini_ocr(monkeypatch) -> None:
    from app.services import resume_parse
    from app.services.resume_files import MIME_PNG

    monkeypatch.setattr(resume_parse, "_use_document_ai", lambda: False)
    monkeypatch.setattr(resume_parse, "_extract_gemini_ocr", lambda *_args, **_kwargs: "IMAGE TEXT")

    assert resume_parse.extract_text(b"\x89PNG", MIME_PNG) == "IMAGE TEXT"


def test_production_storage_uses_supabase_http(monkeypatch) -> None:
    from pydantic import SecretStr

    from app.core.config import Environment
    from app.services import resume_storage

    calls: list[tuple[str, str, dict]] = []

    class FakeResponse:
        status_code = 200
        content = PDF

    def fake_post(url, **kwargs):
        calls.append(("post", url, kwargs))
        return FakeResponse()

    def fake_get(url, **kwargs):
        calls.append(("get", url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(resume_storage.settings, "environment", Environment.PRODUCTION)
    monkeypatch.setattr(resume_storage.settings, "gcs_bucket", "")
    monkeypatch.setattr(resume_storage.settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(resume_storage.settings, "supabase_storage_bucket", "resumes")
    monkeypatch.setattr(resume_storage.settings, "supabase_service_role_key", SecretStr("role-key"))
    monkeypatch.setattr(resume_storage.httpx, "post", fake_post)
    monkeypatch.setattr(resume_storage.httpx, "get", fake_get)

    resume_storage.put_bytes("candidates/x/resume.pdf", PDF, "application/pdf")
    assert resume_storage.get_bytes("candidates/x/resume.pdf") == PDF
    assert "/storage/v1/object/resumes/candidates/x/resume.pdf" in calls[0][1]
    assert calls[0][2]["headers"]["Authorization"] == "Bearer role-key"
    assert "role-key" == calls[0][2]["headers"]["apikey"]


def test_production_storage_uses_gcs(monkeypatch) -> None:
    from pydantic import SecretStr

    from app.core.config import Environment
    from app.services import resume_storage

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

    monkeypatch.setattr(resume_storage.settings, "environment", Environment.PRODUCTION)
    monkeypatch.setattr(resume_storage.settings, "gcs_bucket", "aether-resumes")
    monkeypatch.setattr(resume_storage.settings, "google_cloud_project", "imagi-ai-gpami")
    monkeypatch.setattr(resume_storage, "_gcs_client_bucket", lambda: FakeBucket())

    resume_storage.put_bytes("candidates/x/resume.pdf", PDF, "application/pdf")
    assert resume_storage.get_bytes("candidates/x/resume.pdf") == PDF
    assert store["candidates/x/resume.pdf"] == PDF


def test_enqueue_worker_sends_shared_secret(monkeypatch) -> None:
    from uuid import uuid4

    from pydantic import SecretStr

    from app.services import resume_jobs

    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs.get("headers")
        return FakeResponse()

    monkeypatch.setattr(resume_jobs.settings, "worker_url", "http://worker.test")
    monkeypatch.setattr(resume_jobs.settings, "worker_shared_secret", SecretStr("shared"))
    monkeypatch.setattr(resume_jobs.httpx, "post", fake_post)

    assert resume_jobs._enqueue_worker(uuid4(), object_key="k", content_type="application/pdf") is True
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["X-Worker-Secret"] == "shared"


def test_normalize_parse_result_coerces_string_skills() -> None:
    from app.services.resume_parse import normalize_parse_result

    parsed = normalize_parse_result({"skills": ["Python", "TypeScript"], "technologies": ["FastAPI"]})
    assert parsed["skills"] == [{"skill": "Python"}, {"skill": "TypeScript"}]
    assert parsed["technologies"] == [{"name": "FastAPI"}]
