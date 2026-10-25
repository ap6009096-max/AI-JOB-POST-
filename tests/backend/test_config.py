import pytest
from pydantic import SecretStr

from app.core.config import ConfigurationError, Environment, Settings


def test_local_loads_without_secrets() -> None:
    settings = Settings(_env_file=None, environment=Environment.LOCAL)
    settings.validate_for_environment()
    assert settings.sqlalchemy_database_url.startswith("postgresql://")
    assert settings.supabase_service_role_key is None
    assert "postgresql://postgres:postgres" in settings.sqlalchemy_database_url


def test_local_prefers_api_key_over_vertex_when_both_set() -> None:
    settings = Settings(
        _env_file=None,
        environment=Environment.LOCAL,
        gemini_api_key=SecretStr("local-test-key"),
        google_cloud_project="imagi-ai-gpami",
    )
    assert settings.use_vertex_ai is False
    assert settings.gemini_configured is True


def test_production_missing_secrets_names_variables() -> None:
    settings = Settings(
        _env_file=None,
        environment=Environment.PRODUCTION,
        database_url=None,
        supabase_url="",
        supabase_publishable_key="",
        supabase_service_role_key=None,
        gemini_api_key=None,
        google_cloud_project="",
        gcs_bucket="",
        cloud_tasks_queue="",
        worker_url="",
        worker_shared_secret=None,
        gemini_model="",
    )
    with pytest.raises(ConfigurationError, match="Missing required configuration for production") as exc:
        settings.validate_for_environment()
    message = str(exc.value)
    assert "DATABASE_URL" in message
    assert "SUPABASE_SERVICE_ROLE_KEY" in message
    assert "GOOGLE_CLOUD_PROJECT" in message
    assert "GCS_BUCKET" in message
    assert "CLOUD_TASKS_QUEUE" in message
    assert "WORKER_SHARED_SECRET" in message
    assert "GEMINI_API_KEY" not in message
    assert "SUPABASE_STORAGE_BUCKET" not in message


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
        cloud_tasks_queue="aether-hire-tasks",
        worker_url="https://worker.example.com",
        worker_shared_secret=SecretStr("worker-secret"),
    )
    settings.validate_for_environment()
    assert settings.use_vertex_ai is True
    assert settings.use_gcs_storage is True
    assert settings.use_cloud_tasks is True
    assert settings.gemini_configured is True
    assert "service-role-secret" not in repr(settings)
    assert settings.reddit_client_id is None
    assert "REDDIT_CLIENT_ID" not in settings.missing_required_variables()


def test_production_accepts_vertex_without_api_key() -> None:
    settings = Settings(
        _env_file=None,
        environment=Environment.PRODUCTION,
        database_url=SecretStr("postgresql://user:secret@db:5432/postgres"),
        supabase_url="https://example.supabase.co",
        supabase_publishable_key="sb_publishable_test",
        supabase_service_role_key=SecretStr("service-role-secret"),
        gemini_api_key=None,
        google_cloud_project="imagi-ai-gpami",
        gemini_model="gemini-2.0-flash-001",
        gcs_bucket="bucket",
        cloud_tasks_queue="queue",
        worker_url="https://worker.example.com",
        worker_shared_secret=SecretStr("worker-secret"),
    )
    settings.validate_for_environment()
    assert settings.gemini_configured is True
