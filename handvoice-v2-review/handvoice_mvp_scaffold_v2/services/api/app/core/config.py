from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HANDVOICE_", env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./handvoice.db"
    protocol_path: Path = Path("configs/protocol.v1.yaml")
    storage_root: Path = Path(".local_storage")
    # Optional first-operator seed. On startup an active operator with this key
    # is created if none matches yet, so a fresh deployment is reachable. Leave
    # unset once real operators exist; the API always fails closed without a
    # valid operator key.
    bootstrap_key: str | None = None
    auto_create_schema: bool = True
    maximum_media_bytes: int = 64 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
