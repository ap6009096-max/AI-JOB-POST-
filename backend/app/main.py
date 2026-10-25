import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.candidates import router as candidates_router
from app.api.companies import router as companies_router
from app.api.health import router as health_router
from app.api.internal import router as internal_router
from app.api.jobs import router as jobs_router
from app.api.me import router as me_router
from app.api.me_candidate import router as me_candidate_router
from app.core.config import Environment, settings
from app.core.logging import configure_logging
from app.core.rate_limit import rate_limit_middleware
from app.db.session import dispose_engine
from app.services import gemini_service

logger = logging.getLogger(__name__)

LOCAL_CORS_ORIGIN_REGEX = (
    r"https?://(localhost|127\.0\.0\.1|\[::1\]|"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
    r")(:\d+)?$"
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.validate_for_environment()
    gemini_service.reset_client()
    logger.info(
        "gemini_startup mode=%s configured=%s",
        "vertex" if settings.use_vertex_ai else "api_key",
        gemini_service.is_configured(),
    )
    yield
    dispose_engine()


configure_logging()

app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.middleware("http")(rate_limit_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=(
        LOCAL_CORS_ORIGIN_REGEX if settings.environment is Environment.LOCAL else None
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_request_error path=%s", request.url.path)
    detail = str(exc) if settings.environment is Environment.LOCAL else "Internal server error"
    return JSONResponse(status_code=500, content={"detail": detail})


app.include_router(health_router)
app.include_router(me_router)
app.include_router(me_candidate_router)
app.include_router(internal_router)
app.include_router(companies_router)
app.include_router(jobs_router)
app.include_router(candidates_router)
