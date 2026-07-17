from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HANDVOICE_", env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./handvoice.db"
    redis_url: str = "redis://localhost:6379/0"
    object_storage_bucket: str = "handvoice-dev"
    protocol_path: Path = Path("configs/protocol.v1.yaml")
    auto_create_schema: bool = True


@lru_cache

def get_settings() -> Settings:
    return Settings()
