"""Gemini-backed AI gateway. Callers use app.services.gemini_service, not HTTP routes."""

from app.core.config import settings
from app.services.gemini_service import is_configured


class AIGateway:
    def __init__(self) -> None:
        self.provider = "gemini+vertex"
        self.model = settings.gemini_model
        self.vertex_location = settings.vertex_location

    def status(self) -> str:
        return "configured" if is_configured() else "not_configured"
