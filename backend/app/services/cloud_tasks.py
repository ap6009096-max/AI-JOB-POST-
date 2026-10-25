from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from app.core.config import settings

logger = logging.getLogger(__name__)


def enqueue_parse_resume(candidate_id: UUID, *, object_key: str, content_type: str) -> bool:
    """Enqueue a resume-parse task via Cloud Tasks (OIDC to worker /tasks)."""
    if not settings.use_cloud_tasks or not settings.worker_url:
        return False
    try:
        from google.cloud import tasks_v2
        from google.protobuf import duration_pb2

        client = tasks_v2.CloudTasksClient()
        parent = client.queue_path(
            settings.google_cloud_project,
            settings.cloud_tasks_location,
            settings.cloud_tasks_queue,
        )
        body = {
            "task_type": "parse_resume",
            "reference_id": str(candidate_id),
            "payload": {
                "candidate_id": str(candidate_id),
                "object_key": object_key,
                "content_type": content_type,
            },
        }
        worker_url = settings.worker_url.rstrip("/")
        task: dict[str, Any] = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": f"{worker_url}/tasks",
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(body).encode("utf-8"),
                "oidc_token": {
                    "service_account_email": (
                        f"aether-api@{settings.google_cloud_project}.iam.gserviceaccount.com"
                    ),
                    "audience": worker_url,
                },
            },
            "dispatch_deadline": duration_pb2.Duration(seconds=300),
        }
        client.create_task(request={"parent": parent, "task": task})
        logger.info(
            "cloud_tasks_enqueued candidate_id=%s queue=%s",
            candidate_id,
            settings.cloud_tasks_queue,
        )
        return True
    except Exception:
        logger.exception("cloud_tasks_enqueue_failed candidate_id=%s", candidate_id)
        return False
