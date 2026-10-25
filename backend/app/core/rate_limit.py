from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.config import Environment, settings

# Simple in-process sliding-window limiter suitable for Cloud Run instances.
_WINDOWS: dict[str, deque[float]] = defaultdict(deque)
_LOCK = Lock()

DEFAULT_LIMIT = 120
DEFAULT_WINDOW_SECONDS = 60
UPLOAD_LIMIT = 20
RANKING_LIMIT = 40


def reset_rate_limits() -> None:
    with _LOCK:
        _WINDOWS.clear()


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def check_rate_limit(
    request: Request,
    *,
    limit: int = DEFAULT_LIMIT,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
    bucket: str = "default",
) -> JSONResponse | None:
    if settings.environment is Environment.LOCAL:
        return None
    key = f"{bucket}:{_client_key(request)}"
    now = time.monotonic()
    with _LOCK:
        q = _WINDOWS[key]
        cutoff = now - window_seconds
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= limit:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Try again shortly."},
                headers={"Retry-After": str(window_seconds)},
            )
        q.append(now)
    return None


async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    if path in {"/health", "/ready", "/"} or path.startswith("/v1/internal"):
        return await call_next(request)
    if path.endswith("/resume") and request.method == "POST":
        limited = check_rate_limit(request, limit=UPLOAD_LIMIT, bucket="upload")
    elif "/rank" in path and request.method == "POST":
        limited = check_rate_limit(request, limit=RANKING_LIMIT, bucket="rank")
    else:
        limited = check_rate_limit(request, limit=DEFAULT_LIMIT, bucket="api")
    if limited is not None:
        return limited
    return await call_next(request)
