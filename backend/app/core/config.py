from __future__ import annotations

from enum import StrEnum

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/postgres"


class Environment(StrEnum):
    LOCAL = "local"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class ConfigurationError(RuntimeError):
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    app_name: str = "AI Job Post API"
    environment: Environment = Environment.LOCAL
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    database_url: SecretStr | None = None
    db_pool_size: int = 5
    db_max_overflow: int = 10
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_service_role_key: SecretStr | None = None
    supabase_jwt_audience: str = "authenticated"
    supabase_jwks_url: str = ""

    google_cloud_project: str = ""
    google_cloud_location: str = Field(
        default="",
        validation_alias=AliasChoices(
            "GOOGLE_CLOUD_LOCATION",
            "VERTEX_LOCATION",
            "CLOUD_TASKS_LOCATION",
        ),
    )
    gemini_model: str = "gemini-3.5-flash"
    gemini_api_key: SecretStr | None = None
    github_token: SecretStr | None = None
    reddit_client_id: SecretStr | None = None
    reddit_client_secret: SecretStr | None = None
    reddit_user_agent: str = "AIJobPost/0.1"
    supabase_storage_bucket: str = "resumes"
    gcs_bucket: str = ""
    cloud_tasks_queue: str = ""
    worker_url: str = "http://localhost:8081"
    document_ai_processor_id: str = ""
    resume_local_dir: str = ""
    worker_shared_secret: SecretStr | None = None

    @field_validator(
        "supabase_url",
        "supabase_publishable_key",
        "google_cloud_project",
        "supabase_storage_bucket",
        "gcs_bucket",
        "cloud_tasks_queue",
        "gemini_model",
        "document_ai_processor_id",
        "resume_local_dir",
        "reddit_user_agent",
        mode="before",
    )
    @classmethod
    def blank_to_empty(cls, value: object) -> object:
        if value is None:
            return ""
        return value

    @field_validator(
        "supabase_service_role_key",
        "database_url",
        "worker_shared_secret",
        "gemini_api_key",
        "github_token",
        "reddit_client_id",
        "reddit_client_secret",
        mode="before",
    )
    @classmethod
    def blank_secret_to_none(cls, value: object) -> object:
        if value is None or value == "":
            return None
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url is None:
            return LOCAL_DATABASE_URL
        return self.database_url.get_secret_value()

    @property
    def vertex_location(self) -> str:
        return self.google_cloud_location or "asia-south1"

    @property
    def cloud_tasks_location(self) -> str:
        return self.google_cloud_location or "asia-south1"

    @property
    def resolved_jwks_url(self) -> str:
        if self.supabase_jwks_url:
            return self.supabase_jwks_url
        if self.supabase_url:
            return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        return ""

    @property
    def gemini_configured(self) -> bool:
        return self.gemini_api_key is not None or bool(self.google_cloud_project)

    @property
    def use_vertex_ai(self) -> bool:
        if self.environment is Environment.LOCAL and self.gemini_api_key is not None:
            return False
        return bool(self.google_cloud_project)

    @property
    def use_gcs_storage(self) -> bool:
        return bool(self.gcs_bucket) and self.environment is not Environment.LOCAL

    @property
    def use_cloud_tasks(self) -> bool:
        return (
            bool(self.cloud_tasks_queue)
            and bool(self.google_cloud_project)
            and self.environment is not Environment.LOCAL
        )

    def missing_required_variables(self) -> list[str]:
        missing: list[str] = []
        env = self.environment

        if env is Environment.LOCAL:
            return missing

        if self.database_url is None:
            missing.append("DATABASE_URL")
        if not self.supabase_url:
            missing.append("SUPABASE_URL")
        if not self.supabase_publishable_key:
            missing.append("SUPABASE_PUBLISHABLE_KEY")

        if env in {Environment.STAGING, Environment.PRODUCTION}:
            if self.supabase_service_role_key is None:
                missing.append("SUPABASE_SERVICE_ROLE_KEY")
            if not self.google_cloud_project:
                missing.append("GOOGLE_CLOUD_PROJECT")
            if not self.gemini_model:
                missing.append("GEMINI_MODEL")
            if not self.gcs_bucket:
                missing.append("GCS_BUCKET")
            if not self.cloud_tasks_queue:
                missing.append("CLOUD_TASKS_QUEUE")
            if not self.worker_url:
                missing.append("WORKER_URL")
            if self.worker_shared_secret is None:
                missing.append("WORKER_SHARED_SECRET")

        return missing

    def validate_for_environment(self) -> None:
        missing = self.missing_required_variables()
        if missing:
            raise ConfigurationError(
                f"Missing required configuration for {self.environment}: {', '.join(missing)}"
            )


settings = Settings()
