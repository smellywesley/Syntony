from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import subprocess

from services.api.app.core.config import get_settings


@dataclass(frozen=True, slots=True)
class MediaProbeResult:
    path: Path
    duration_ms: int
    video_fps: float
    audio_sample_rate: int
    video_start_ms: int
    audio_start_ms: int
    usable_end_ms: int


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
        raise ValueError("uploaded media does not exist")
    return candidate


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
    if abs(video_start - audio_start) > 0.100:
        raise ValueError("audio and video stream starts differ by more than 100 ms")
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
