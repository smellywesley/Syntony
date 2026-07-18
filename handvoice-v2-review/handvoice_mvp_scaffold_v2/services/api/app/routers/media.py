from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from services.api.app.core.config import get_settings
from services.api.app.core.security import require_operator
from services.api.app.schemas.api import MediaUploadRead

router = APIRouter(
    prefix="/v1/media",
    tags=["media"],
    dependencies=[Depends(require_operator)],
)

ALLOWED_SUFFIXES = {".mp4", ".webm", ".mov"}
CHUNK_BYTES = 1024 * 1024


@router.post("", response_model=MediaUploadRead, status_code=status.HTTP_201_CREATED)
async def upload_media(file: UploadFile = File(...)) -> MediaUploadRead:
    suffix = Path(file.filename or "capture.webm").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="media must be MP4, WebM, or MOV")

    settings = get_settings()
    root = settings.storage_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    storage_key = f"incoming/{uuid4().hex}{suffix}"
    destination = (root / storage_key).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(f"{destination.suffix}.partial")
    digest = sha256()
    size_bytes = 0
    try:
        with temporary.open("xb") as output:
            while chunk := await file.read(CHUNK_BYTES):
                size_bytes += len(chunk)
                if size_bytes > settings.maximum_media_bytes:
                    raise HTTPException(status_code=413, detail="media exceeds configured size limit")
                digest.update(chunk)
                output.write(chunk)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    return MediaUploadRead(
        storage_key=storage_key,
        sha256=digest.hexdigest(),
        size_bytes=size_bytes,
    )
