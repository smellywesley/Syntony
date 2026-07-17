from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from services.api.app.core.config import get_settings
from services.api.app.db.base import Base
from services.api.app.db.session import engine
from services.api.app.routers import health, media, participants, sessions

# Placeholder keys shipped in config defaults, docker-compose, and .env.example.
# The API refuses to serve with any of these: they guard participant media.
KNOWN_DEFAULT_API_KEYS = frozenset(
    {
        "local-development-only-change-me",
        "change-this-api-key",
        "replace-with-a-long-random-value",
    }
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if get_settings().api_key in KNOWN_DEFAULT_API_KEYS:
        raise RuntimeError(
            "HANDVOICE_API_KEY is a known placeholder value; set a unique secret "
            "(e.g. python -c \"import secrets; print(secrets.token_urlsafe(32))\") before serving"
        )
    if get_settings().auto_create_schema:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="HandVoice API",
    version="0.2.0",
    description="Competition MVP for synchronized hand–speech measurement. Synchronous analysis only; no diagnosis.",
    lifespan=lifespan,
)
app.include_router(health.router)
app.include_router(participants.router)
app.include_router(sessions.router)
app.include_router(media.router)

capture_dist = Path("apps/capture-web/dist")
if capture_dist.is_dir():
    app.mount("/capture", StaticFiles(directory=capture_dist, html=True), name="capture")
