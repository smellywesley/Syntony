import asyncio
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import os
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException, UploadFile

from services.api.app.core.config import get_settings
from services.api.app.models.entities import Operator
from services.api.app.routers.media import upload_media
from services.api.app.services.media import (
    StorageObjectNotFound,
    claim_uploaded_media,
    discard_pending_upload,
    discard_uploaded_media,
    purge_stale_pending_uploads,
)


def _operator() -> Operator:
    return Operator(id=uuid4(), label="test", key_hash="0" * 64)


def test_media_upload_uses_generated_contained_key(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HANDVOICE_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("HANDVOICE_MAXIMUM_MEDIA_BYTES", "1024")
    get_settings.cache_clear()
    try:
        result = asyncio.run(
            upload_media(
                UploadFile(filename="../../capture.webm", file=BytesIO(b"safe")),
                _operator(),
            )
        )
        assert result.storage_key.startswith("incoming/")
        assert ".." not in result.storage_key
        assert (tmp_path / result.storage_key).read_bytes() == b"safe"
    finally:
        get_settings.cache_clear()


def test_media_upload_removes_partial_file_when_size_limit_is_exceeded(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("HANDVOICE_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("HANDVOICE_MAXIMUM_MEDIA_BYTES", "3")
    get_settings.cache_clear()
    try:
        with pytest.raises(HTTPException) as error:
            asyncio.run(
                upload_media(
                    UploadFile(filename="capture.mp4", file=BytesIO(b"large")),
                    _operator(),
                )
            )
        assert error.value.status_code == 413
        assert not list(tmp_path.rglob("*.partial"))
    finally:
        get_settings.cache_clear()


def test_concurrent_pending_upload_claim_has_exactly_one_owner(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("HANDVOICE_STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    try:
        pending = tmp_path / "incoming" / "capture.webm"
        pending.parent.mkdir(parents=True)
        pending.write_bytes(b"capture")
        barrier = Barrier(2)

        def attempt_claim():
            barrier.wait()
            try:
                return claim_uploaded_media("incoming/capture.webm")
            except StorageObjectNotFound:
                return None

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: attempt_claim(), range(2)))
        claims = [claim for claim in results if claim is not None]

        assert len(claims) == 1
        claimed = claims[0]
        assert claimed.storage_key.startswith("processing/")
        assert claimed.path.read_bytes() == b"capture"
        assert not pending.exists()
    finally:
        get_settings.cache_clear()


def test_idempotent_duplicate_checksum_is_verified_before_deletion(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("HANDVOICE_STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    pending = tmp_path / "incoming" / "wrong.webm"
    pending.parent.mkdir(parents=True)
    pending.write_bytes(b"wrong capture")
    try:
        with pytest.raises(ValueError, match="checksum"):
            discard_pending_upload("incoming/wrong.webm", expected_sha256="0" * 64)
        assert not pending.exists()
        assert not list((tmp_path / "processing").iterdir())
    finally:
        get_settings.cache_clear()


def test_discard_retries_transient_file_lock(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("HANDVOICE_STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    target = tmp_path / "processing" / "capture.webm"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"capture")
    real_unlink = Path.unlink
    calls = 0

    def flaky_unlink(path: Path, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise PermissionError("temporarily locked")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", flaky_unlink)
    try:
        assert discard_uploaded_media("processing/capture.webm") is True
        assert calls == 3
        assert not target.exists()
    finally:
        get_settings.cache_clear()


def test_stale_pending_uploads_are_expired_but_fresh_uploads_remain(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("HANDVOICE_STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    incoming = tmp_path / "incoming"
    incoming.mkdir(parents=True)
    stale = incoming / "stale.webm"
    fresh = incoming / "fresh.webm"
    stale.write_bytes(b"stale")
    fresh.write_bytes(b"fresh")
    os.utime(stale, (1, 1))
    try:
        assert purge_stale_pending_uploads(max_age_seconds=60) == 1
        assert not stale.exists()
        assert fresh.exists()
    finally:
        get_settings.cache_clear()
