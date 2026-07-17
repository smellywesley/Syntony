from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.api.app.core.config import get_settings
from services.api.app.db.base import Base
from services.api.app.db.session import engine
from services.api.app.routers import health, participants, sessions


@asynccontextmanager
async def lifespan(_: FastAPI):
    if get_settings().auto_create_schema:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="HandVoice API",
    version="0.1.0",
    description="Research measurement API. This service does not diagnose disease.",
    lifespan=lifespan,
)
app.include_router(health.router)
app.include_router(participants.router)
app.include_router(sessions.router)
