from __future__ import annotations

import tempfile
from pathlib import Path
from urllib.parse import quote

import httpx

from app.config import Environment, settings


class ResumeStorageError(RuntimeError):
    pass


def local_root() -> Path:
    if settings.resume_local_dir:
        return Path(settings.resume_local_dir)
    return Path(tempfile.gettempdir()) / "ai-job-post-resumes"


def get_bytes(object_key: str) -> bytes:
    if settings.use_gcs_storage:
        return _gcs_get(object_key)
    if _use_supabase_storage():
        return _supabase_get(object_key)
    path = local_root() / object_key
    if not path.is_file():
        raise ResumeStorageError("Resume file is no longer available")
    return path.read_bytes()


def _use_supabase_storage() -> bool:
    return (
        bool(settings.supabase_storage_bucket)
        and settings.environment is not Environment.LOCAL
        and not settings.gcs_bucket
        and bool(settings.supabase_url)
        and settings.supabase_service_role_key is not None
    )


def _gcs_client_bucket():
    from google.cloud import storage

    client = storage.Client(project=settings.google_cloud_project or None)
    return client.bucket(settings.gcs_bucket)


def _gcs_get(object_key: str) -> bytes:
    blob = _gcs_client_bucket().blob(object_key)
    if not blob.exists():
        raise ResumeStorageError("Resume file is no longer available")
    return blob.download_as_bytes()


def _object_url(object_key: str) -> str:
    encoded = "/".join(quote(part, safe="") for part in object_key.split("/") if part)
    return (
        f"{settings.supabase_url.rstrip('/')}/storage/v1/object/"
        f"{quote(settings.supabase_storage_bucket, safe='')}/{encoded}"
    )


def _storage_headers() -> dict[str, str]:
    secret = settings.supabase_service_role_key
    if secret is None:
        raise ResumeStorageError("Resume file is no longer available")
    token = secret.get_secret_value()
    return {
        "Authorization": f"Bearer {token}",
        "apikey": token,
    }


def _supabase_get(object_key: str) -> bytes:
    response = httpx.get(
        _object_url(object_key),
        headers=_storage_headers(),
        timeout=30.0,
    )
    if response.status_code >= 400 or response.content is None:
        raise ResumeStorageError("Resume file is no longer available")
    return response.content
