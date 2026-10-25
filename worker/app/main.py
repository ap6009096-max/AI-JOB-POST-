from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, status
from jwt import PyJWKClient

from app.config import Environment, settings
from app.logging import configure_logging
from app.resume_jobs import run_parse_resume
from app.tasks import TaskPayload

configure_logging()
logger = logging.getLogger(__name__)

_GOOGLE_JWKS = PyJWKClient("https://www.googleapis.com/oauth2/v3/certs", cache_keys=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.validate_for_environment()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


def _shared_secret_ok(provided: str) -> bool:
    expected = settings.worker_shared_secret
    if expected is None:
        return settings.environment is Environment.LOCAL and not provided
    return bool(provided) and provided == expected.get_secret_value()


def _oidc_ok(authorization: str) -> bool:
    if settings.environment is Environment.LOCAL:
        return False
    if not authorization.lower().startswith("bearer "):
        return False
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return False
    try:
        key = _GOOGLE_JWKS.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        email = str(claims.get("email") or "")
        if not email.endswith(".iam.gserviceaccount.com"):
            return False
        if claims.get("email_verified") is False:
            return False
        iss = str(claims.get("iss") or "")
        return iss in {"https://accounts.google.com", "accounts.google.com"}
    except Exception:
        logger.info("worker_oidc_verification_failed")
        return False


def require_worker_auth(
    x_worker_secret: str = Header(default="", alias="X-Worker-Secret"),
    authorization: str = Header(default=""),
) -> None:
    if _shared_secret_ok(x_worker_secret):
        return
    if _oidc_ok(authorization):
        return
    if settings.worker_shared_secret is None and settings.environment is Environment.LOCAL:
        return
    if settings.worker_shared_secret is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Worker enqueue is not configured",
        )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid worker credentials")


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "aether-worker",
        "environment": str(settings.environment),
    }


@app.post("/tasks")
def enqueue_task(
    task: TaskPayload,
    _: None = Depends(require_worker_auth),
) -> dict[str, str]:
    logger.info("task_accepted task_type=%s reference_id=%s", task.task_type, task.reference_id)
    if task.task_type != "parse_resume":
        return {
            "status": "accepted",
            "task_type": task.task_type,
            "reference_id": task.reference_id,
            "detail": "Queued for future AI processing",
        }

    # Cloud Tasks (non-local) waits for completion so retries work.
    # Local/dev accepts immediately and processes in a background thread.
    if settings.environment is Environment.LOCAL:
        threading.Thread(target=run_parse_resume, args=(task,), daemon=True).start()
        return {
            "status": "accepted",
            "task_type": task.task_type,
            "reference_id": task.reference_id,
            "detail": "Resume parse queued",
        }

    result = run_parse_resume(task)
    status_value = result.get("status", "failed")
    return {
        "status": status_value,
        "task_type": task.task_type,
        "reference_id": task.reference_id,
        "detail": (
            "Resume parse completed"
            if status_value == "succeeded"
            else result.get("error", "Resume parse failed")
        ),
    }
