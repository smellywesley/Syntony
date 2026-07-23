from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import logging
from math import isfinite
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

from services.api.app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MediaProbeResult:
    path: Path
    duration_ms: int
    video_fps: float
    audio_sample_rate: int
    video_start_ms: int
    audio_start_ms: int
    usable_end_ms: int


@dataclass(frozen=True, slots=True)
class ClaimedUpload:
    storage_key: str
    path: Path


class StorageObjectNotFound(ValueError):
    """Raised when an upload no longer exists at the supplied storage key."""


class MediaCleanupError(RuntimeError):
    """Raised when an unaccepted upload cannot be removed after bounded retries."""


def _fraction(value: str) -> float:
    numerator, denominator = value.split("/", maxsplit=1)
    return float(numerator) / float(denominator) if float(denominator) else 0.0


def _seconds(value: object, *, fallback: float | None = None) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        if fallback is None:
            raise ValueError("recording has incomplete stream timing metadata") from None
        return fallback
    if not isfinite(parsed):
        if fallback is None:
            raise ValueError("recording has non-finite stream timing metadata")
        return fallback
    return parsed


def resolve_storage_key(storage_key: str) -> Path:
    root = get_settings().storage_root.resolve()
    candidate = (root / storage_key).resolve()
    if candidate == root or root not in candidate.parents:
        raise ValueError("storage key escapes the configured storage root")
    if not candidate.is_file():
        raise StorageObjectNotFound("uploaded media does not exist")
    return candidate


def claim_uploaded_media(storage_key: str) -> ClaimedUpload:
    """Atomically take ownership of one pending upload for a measurement request.

    Uploads are accepted only from ``incoming/``. Moving the object on the same
    filesystem is atomic, so concurrent submissions cannot both own and later
    delete the same media object.
    """
    purge_stale_pending_uploads()
    root = get_settings().storage_root.resolve()
    key_path = Path(storage_key)
    if (
        key_path.is_absolute()
        or len(key_path.parts) != 2
        or key_path.parts[0] != "incoming"
        or key_path.parts[1] in {".", ".."}
    ):
        raise ValueError("only pending incoming media can be claimed")
    # Upload keys are server-generated as exactly ``incoming/<uuid>.<suffix>``.
    # Lexical construction avoids Windows ``Path.resolve`` races on a file that
    # another claimant may move between resolution and validation.
    source = root / key_path
    if not source.is_file():
        raise StorageObjectNotFound("uploaded media does not exist")

    suffix = source.suffix.lower()
    claimed_key = f"processing/{uuid4().hex}{suffix}"
    # ``claimed_key`` is generated entirely by the server. Keep this lexical
    # construction under the already-resolved root; resolving two not-yet-created
    # siblings concurrently is unreliable on Windows and is unnecessary here.
    destination = root / claimed_key
    destination.parent.mkdir(parents=True, exist_ok=True)
    claim_lock = source.with_name(f"{source.name}.claim")
    try:
        descriptor = os.open(claim_lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise StorageObjectNotFound("uploaded media has already been claimed") from exc
    os.close(descriptor)
    try:
        source.replace(destination)
    except FileNotFoundError as exc:
        raise StorageObjectNotFound("uploaded media has already been claimed") from exc
    finally:
        try:
            claim_lock.unlink(missing_ok=True)
        except OSError:
            # The media has already moved into the uniquely owned path. A stale
            # zero-byte lock is harmless and is removed by the pending TTL sweep.
            logger.warning("Could not remove a completed media claim lock")
    return ClaimedUpload(storage_key=claimed_key, path=destination)


def verify_sha256(path: Path, expected: str) -> None:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected.lower():
        raise ValueError("media checksum does not match")


def probe_media(path: Path) -> MediaProbeResult:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,avg_frame_rate,sample_rate,start_time,duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=20)
    except FileNotFoundError as exc:
        raise RuntimeError("ffprobe is required for media validation") from exc
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError("media cannot be validated by ffprobe") from exc

    payload = json.loads(completed.stdout)
    duration_seconds = _seconds(payload.get("format", {}).get("duration"), fallback=0.0)
    duration_ms = round(duration_seconds * 1000)
    video_streams = [stream for stream in payload.get("streams", []) if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in payload.get("streams", []) if stream.get("codec_type") == "audio"]
    if not video_streams or not audio_streams:
        raise ValueError("recording must contain synchronized video and audio tracks")
    if not 14000 <= duration_ms <= 17000:
        raise ValueError("recording duration must be between 14 and 17 seconds")
    fps = _fraction(video_streams[0].get("avg_frame_rate", "0/1"))
    sample_rate = int(audio_streams[0].get("sample_rate") or 0)
    if fps <= 0 or sample_rate < 8000:
        raise ValueError("recording has invalid video or audio timing metadata")
    video_start = _seconds(video_streams[0].get("start_time"), fallback=0.0)
    audio_start = _seconds(audio_streams[0].get("start_time"), fallback=0.0)
    video_duration = _seconds(video_streams[0].get("duration"), fallback=duration_seconds)
    audio_duration = _seconds(audio_streams[0].get("duration"), fallback=duration_seconds)
    usable_end_ms = round(min(video_start + video_duration, audio_start + audio_duration) * 1000)
    if usable_end_ms <= 0:
        raise ValueError("recording has no usable synchronized duration")
    return MediaProbeResult(
        path=path,
        duration_ms=duration_ms,
        video_fps=fps,
        audio_sample_rate=sample_rate,
        video_start_ms=round(video_start * 1000),
        audio_start_ms=round(audio_start * 1000),
        usable_end_ms=usable_end_ms,
    )


def validate_uploaded_media(
    storage_key: str,
    expected_sha256: str,
    *,
    required_end_ms: int,
) -> MediaProbeResult:
    path = resolve_storage_key(storage_key)
    verify_sha256(path, expected_sha256)
    result = probe_media(path)
    if required_end_ms > result.usable_end_ms:
        raise ValueError("active measurement window extends beyond synchronized media")
    return result


def discard_uploaded_media(storage_key: str, *, attempts: int = 3) -> bool:
    """Delete one contained object with bounded retries for transient file locks."""
    if attempts < 1:
        raise ValueError("cleanup attempts must be positive")
    root = get_settings().storage_root.resolve()
    candidate = (root / storage_key).resolve()
    if candidate == root or root not in candidate.parents:
        raise ValueError("storage key escapes the configured storage root")
    if not candidate.is_file():
        return False
    last_error: OSError | None = None
    for attempt in range(attempts):
        try:
            candidate.unlink()
            return True
        except FileNotFoundError:
            return False
        except OSError as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.05 * (attempt + 1))
    raise MediaCleanupError(
        f"privacy cleanup failed after {attempts} attempts"
    ) from last_error


def discard_pending_upload(
    storage_key: str,
    *,
    expected_sha256: str | None = None,
) -> bool:
    """Atomically claim and remove a pending upload, if it still exists."""
    try:
        claimed = claim_uploaded_media(storage_key)
    except StorageObjectNotFound:
        return False
    if expected_sha256 is not None:
        try:
            verify_sha256(claimed.path, expected_sha256)
        except ValueError:
            discard_uploaded_media(claimed.storage_key)
            raise
    return discard_uploaded_media(claimed.storage_key)


def purge_stale_pending_uploads(*, max_age_seconds: int = 3600) -> int:
    """Remove completed uploads left in ``incoming/`` beyond their pending TTL.

    This is the no-migration fallback for uploads whose measurement request is
    rejected by request-schema validation before the measurement route runs.
    It is invoked opportunistically before claims and is also executable with
    ``python -m services.api.app.services.media``.
    """
    if max_age_seconds < 0:
        raise ValueError("pending upload maximum age must be non-negative")
    root = get_settings().storage_root.resolve()
    incoming = (root / "incoming").resolve()
    if incoming == root or root not in incoming.parents or not incoming.is_dir():
        return 0
    cutoff = time.time() - max_age_seconds
    removed = 0
    for candidate in incoming.iterdir():
        if not candidate.is_file() or candidate.suffix == ".partial":
            continue
        try:
            if candidate.stat().st_mtime > cutoff:
                continue
            relative_key = candidate.resolve().relative_to(root).as_posix()
            removed += int(discard_uploaded_media(relative_key))
        except (FileNotFoundError, ValueError):
            continue
    return removed


if __name__ == "__main__":
    print(f"Removed {purge_stale_pending_uploads()} stale pending upload(s).")
