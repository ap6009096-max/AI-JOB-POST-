from pydantic import SecretStr

from app.config import ConfigurationError, Environment, Settings


def test_production_complete_config_passes() -> None:
    settings = Settings(
        _env_file=None,
        environment=Environment.PRODUCTION,
        database_url=SecretStr("postgresql://user:secret@db:5432/postgres"),
        supabase_url="https://example.supabase.co",
        supabase_publishable_key="sb_publishable_test",
        supabase_service_role_key=SecretStr("service-role-secret"),
        google_cloud_project="imagi-ai-gpami",
        gemini_model="gemini-2.0-flash-001",
        gcs_bucket="aether-hire-resumes",
        backend_url="https://api.example.com",
        worker_shared_secret=SecretStr("worker-secret"),
    )
    settings.validate_for_environment()
    assert settings.use_vertex_ai is True
    assert settings.use_gcs_storage is True
    assert settings.gemini_configured is True
    assert settings.gemini_api_key is None


def test_gemini_configured_with_project_and_no_api_key() -> None:
    settings = Settings(
        _env_file=None,
        environment=Environment.PRODUCTION,
        database_url=SecretStr("postgresql://user:secret@db:5432/postgres"),
        supabase_url="https://example.supabase.co",
        supabase_publishable_key="sb_publishable_test",
        supabase_service_role_key=SecretStr("service-role-secret"),
        google_cloud_project="imagi-ai-gpami",
        gemini_model="gemini-2.0-flash-001",
        gemini_api_key=None,
        gcs_bucket="aether-hire-resumes",
        backend_url="https://api.example.com",
        worker_shared_secret=SecretStr("worker-secret"),
    )
    assert settings.gemini_configured is True
    assert settings.use_vertex_ai is True


def test_production_requires_google_cloud_project() -> None:
    settings = Settings(
        _env_file=None,
        environment=Environment.PRODUCTION,
        database_url=SecretStr("postgresql://user:secret@db:5432/postgres"),
        supabase_url="https://example.supabase.co",
        supabase_publishable_key="sb_publishable_test",
        supabase_service_role_key=SecretStr("service-role-secret"),
        gemini_api_key=None,
        google_cloud_project="",
        gcs_bucket="bucket",
        backend_url="https://api.example.com",
        worker_shared_secret=SecretStr("worker-secret"),
    )
    try:
        settings.validate_for_environment()
    except ConfigurationError as exc:
        assert "GOOGLE_CLOUD_PROJECT" in str(exc)
        assert "GEMINI_API_KEY" not in str(exc)
        return
    raise AssertionError("expected ConfigurationError")
