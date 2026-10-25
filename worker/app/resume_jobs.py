from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.resume_parse import ResumeParseError, parse_resume_bytes
from app.resume_storage import ResumeStorageError, get_bytes
from app.tasks import TaskPayload

logger = logging.getLogger(__name__)


def run_parse_resume(task: TaskPayload) -> dict[str, str]:
    payload = task.payload or {}
    candidate_id = str(payload.get("candidate_id") or task.reference_id)
    object_key = str(payload.get("object_key") or "")
    content_type = str(payload.get("content_type") or "")
    logger.info("resume_processing_started candidate_id=%s object_key=%s", candidate_id, object_key)
    if not object_key or not content_type:
        error = "Resume processing payload is incomplete"
        _callback(candidate_id, status="failed", error=error)
        return {"status": "failed", "error": error}
    try:
        data = get_bytes(object_key)
        text, parsed = parse_resume_bytes(data, content_type)
        _callback(candidate_id, status="succeeded", text=text, parse_result=parsed)
        logger.info("resume_processing_succeeded candidate_id=%s", candidate_id)
        return {"status": "succeeded"}
    except ResumeParseError as exc:
        logger.info("resume_%s_failed candidate_id=%s", exc.stage, candidate_id)
        _callback(candidate_id, status="failed", error=str(exc))
        return {"status": "failed", "error": str(exc)}
    except ResumeStorageError:
        error = "Could not process this resume. Try another file."
        logger.info("resume_ocr_failed candidate_id=%s", candidate_id)
        _callback(candidate_id, status="failed", error=error)
        return {"status": "failed", "error": error}
    except Exception:
        logger.exception("resume_processing_failed candidate_id=%s", candidate_id)
        error = "Could not process this resume. Try another file."
        _callback(candidate_id, status="failed", error=error)
        return {"status": "failed", "error": error}


def _callback(
    candidate_id: str,
    *,
    status: str,
    text: str = "",
    parse_result: dict | None = None,
    error: str = "",
) -> None:
    if not settings.backend_url:
        return
    headers = {"Content-Type": "application/json"}
    secret = settings.worker_shared_secret
    if secret is not None:
        headers["X-Worker-Secret"] = secret.get_secret_value()
    try:
        httpx.post(
            f"{settings.backend_url.rstrip('/')}/v1/internal/worker/resume-complete",
            headers=headers,
            json={
                "candidate_id": candidate_id,
                "status": status,
                "text": text,
                "parse_result": parse_result,
                "error": error,
            },
            timeout=10.0,
        )
    except Exception:
        logger.exception("resume_callback_failed candidate_id=%s", candidate_id)
