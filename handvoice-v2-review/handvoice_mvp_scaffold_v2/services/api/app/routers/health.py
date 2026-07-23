import os
import shutil

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from services.api.app.core.config import get_settings
from services.api.app.db.session import SessionLocal
from services.api.app.schemas.api import HealthRead, ReadinessRead

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthRead)
def health() -> HealthRead:
    return HealthRead(status="ok", environment=get_settings().environment)


@router.get("/ready", response_model=ReadinessRead)
def readiness(response: Response) -> ReadinessRead:
    settings = get_settings()
    database_ready = False
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        database_ready = True
    except Exception:
        database_ready = False

    storage_root = settings.storage_root.resolve()
    storage_ready = storage_root.is_dir() and os.access(storage_root, os.W_OK)
    components = {
        "database": database_ready,
        "storage": storage_ready,
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "ffprobe": shutil.which("ffprobe") is not None,
    }
    ready = all(components.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessRead(
        status="ready" if ready else "not_ready",
        components=components,
    )
