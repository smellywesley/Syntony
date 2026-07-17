from fastapi import APIRouter

from services.api.app.core.config import get_settings
from services.api.app.schemas.api import HealthRead

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthRead)
def health() -> HealthRead:
    return HealthRead(status="ok", environment=get_settings().environment)
