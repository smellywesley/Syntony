"""Regression tests for the pre-ship review fixes: placeholder bootstrap keys
must not seed a working operator, and a task instance can never accumulate two
recordings."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.app import main
from services.api.app.core.config import Settings
from services.api.app.db.base import Base
from services.api.app.models.entities import Recording


def _recording(task_id) -> Recording:
    return Recording(
        task_instance_id=task_id,
        object_uri="file://capture.mp4",
        sha256="0" * 64,
        duration_ms=15000,
    )


def test_second_recording_for_same_task_instance_is_rejected():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    task_id = uuid4()
    with Session(engine) as db:
        db.add(_recording(task_id))
        db.commit()
        db.add(_recording(task_id))
        with pytest.raises(IntegrityError):
            db.commit()


@pytest.mark.parametrize(
    "placeholder",
    sorted(main.KNOWN_DEFAULT_KEYS),
)
def test_server_refuses_placeholder_bootstrap_key(placeholder, monkeypatch):
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(bootstrap_key=placeholder, auto_create_schema=False),
    )
    with pytest.raises(RuntimeError, match="placeholder"):
        with TestClient(main.app):
            pass


def test_server_starts_with_real_bootstrap_key(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(bootstrap_key="a-genuinely-unique-secret", auto_create_schema=False),
    )
    # Seeding needs a live DB; the seeding logic itself is covered by
    # test_operator_auth, so stub it here to isolate the startup guard.
    monkeypatch.setattr(main, "seed_bootstrap_operator", lambda *args, **kwargs: None)
    with TestClient(main.app):
        pass


def test_server_starts_without_bootstrap_key(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(bootstrap_key=None, auto_create_schema=False),
    )
    with TestClient(main.app):
        pass
