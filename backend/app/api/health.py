import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine
from app.schemas.health import HealthResponse
from app.services.ai import AIGateway

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


def _health() -> HealthResponse:
    database_status = "ok"
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("database_health_failed")
        database_status = "error"

    return HealthResponse(
        status="ok" if database_status == "ok" else "degraded",
        service="ai-job-post-backend",
        environment=str(settings.environment),
        database=database_status,
        ai=AIGateway().status(),
    )


@router.get("/", response_model=HealthResponse)
def root() -> HealthResponse:
    return _health()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return _health()


@router.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready", "service": "ai-job-post-backend"}
