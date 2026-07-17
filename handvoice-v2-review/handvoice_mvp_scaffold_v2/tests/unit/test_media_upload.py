import asyncio
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile

from services.api.app.core.config import get_settings
from services.api.app.routers.media import upload_media


def test_media_upload_uses_generated_contained_key(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HANDVOICE_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("HANDVOICE_MAXIMUM_MEDIA_BYTES", "1024")
    get_settings.cache_clear()
    try:
        result = asyncio.run(upload_media(UploadFile(filename="../../capture.webm", file=BytesIO(b"safe"))))
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
            asyncio.run(upload_media(UploadFile(filename="capture.mp4", file=BytesIO(b"large"))))
        assert error.value.status_code == 413
        assert not list(tmp_path.rglob("*.partial"))
    finally:
        get_settings.cache_clear()
