from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from services.api.app.core.config import get_settings
from services.api.app.db.base import Base
from services.api.app.db.session import SessionLocal, engine
from services.api.app.routers import health, media, participants, sessions
from services.api.app.services.operators import seed_bootstrap_operator

# Placeholder values that must never authenticate a real deployment. A
# bootstrap key set to any of these is rejected so a shipped default cannot
# accidentally seed a working operator.
KNOWN_DEFAULT_KEYS = frozenset(
    {
        "local-development-only-change-me",
        "change-this-api-key",
        "replace-with-a-long-random-value",
    }
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.demo_bypass_operator_auth and settings.environment != "native-demo":
        raise RuntimeError(
            "HANDVOICE_DEMO_BYPASS_OPERATOR_AUTH is allowed only when "
            "HANDVOICE_ENVIRONMENT=native-demo"
        )
    if settings.auto_create_schema:
        Base.metadata.create_all(bind=engine)
    settings.storage_root.resolve().mkdir(parents=True, exist_ok=True)
    bootstrap = settings.bootstrap_key
    if bootstrap:
        if bootstrap in KNOWN_DEFAULT_KEYS:
            raise RuntimeError(
                "HANDVOICE_BOOTSTRAP_KEY is a known placeholder value; set a unique "
                'secret (e.g. python -c "import secrets; print(secrets.token_urlsafe(32))")'
            )
        if len(bootstrap.encode("utf-8")) < 32:
            raise RuntimeError(
                "HANDVOICE_BOOTSTRAP_KEY must contain at least 32 bytes; generate "
                'one with python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        with SessionLocal() as db:
            seed_bootstrap_operator(db, bootstrap)
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
