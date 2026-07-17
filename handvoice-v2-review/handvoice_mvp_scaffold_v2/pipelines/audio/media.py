from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

import numpy as np

from pipelines.audio.extractor import merge_intervals


@dataclass(frozen=True, slots=True)
class AudioEventExtraction:
    voiced_intervals: tuple[tuple[int, int], ...]
    onset_times_ms: tuple[int, ...]


def decode_audio_segment(
    path: Path,
    *,
    start_ms: int,
    duration_ms: int,
    sample_rate: int = 16000,
) -> np.ndarray:
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-ss",
        f"{start_ms / 1000:.3f}",
        "-t",
        f"{duration_ms / 1000:.3f}",
        "-i",
        str(path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "s16le",
        "pipe:1",
    ]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, timeout=30)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg is required for audio extraction") from exc
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError("audio track could not be decoded") from exc
    samples = np.frombuffer(completed.stdout, dtype="<i2").astype(np.float64) / 32768.0
    if samples.size == 0:
        raise ValueError("decoded audio segment is empty")
    return samples


def extract_energy_events(
    samples: np.ndarray,
    *,
    sample_rate: int,
    frame_ms: int = 20,
    hop_ms: int = 10,
    minimum_onset_separation_ms: int = 100,
) -> AudioEventExtraction:
    """Extract a conservative energy-based speech mask and candidate syllable onsets.

    This is an executable MVP baseline, not a validated DDK segmenter. The output
    must be compared with manual annotation before use as a research endpoint.
    """
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    array = np.asarray(samples, dtype=np.float64).reshape(-1)
    if array.size == 0:
        return AudioEventExtraction((), ())
    frame_size = max(1, round(sample_rate * frame_ms / 1000))
    hop_size = max(1, round(sample_rate * hop_ms / 1000))
    if array.size < frame_size:
        array = np.pad(array, (0, frame_size - array.size))
    starts = np.arange(0, array.size - frame_size + 1, hop_size)
    rms = np.array([np.sqrt(np.mean(array[start : start + frame_size] ** 2)) for start in starts])
    if not np.any(np.isfinite(rms)) or float(np.max(rms)) <= 1e-8:
        return AudioEventExtraction((), ())

    noise = float(np.quantile(rms, 0.20))
    high = float(np.quantile(rms, 0.90))
    voiced_threshold = max(noise * 2.5, noise + 0.12 * max(1e-8, high - noise))
    voiced = rms >= voiced_threshold

    raw_intervals: list[tuple[int, int]] = []
    interval_start: int | None = None
    for index, state in enumerate(voiced):
        frame_start_ms = round(starts[index] * 1000 / sample_rate)
        frame_end_ms = frame_start_ms + frame_ms
        if state and interval_start is None:
            interval_start = frame_start_ms
        if not state and interval_start is not None:
            raw_intervals.append((interval_start, frame_start_ms))
            interval_start = None
        if state and index == len(voiced) - 1 and interval_start is not None:
            raw_intervals.append((interval_start, frame_end_ms))
    duration_ms = round(array.size * 1000 / sample_rate)
    intervals = merge_intervals(raw_intervals, lower_bound_ms=0, upper_bound_ms=duration_ms)

    smoothed = np.convolve(rms, np.ones(3) / 3, mode="same")
    onset_threshold = max(noise * 3.0, noise + 0.30 * max(1e-8, high - noise))
    candidates: list[tuple[int, float]] = []
    for index in range(1, len(smoothed) - 1):
        value = float(smoothed[index])
        if value >= onset_threshold and value > smoothed[index - 1] and value >= smoothed[index + 1]:
            candidates.append((round(starts[index] * 1000 / sample_rate), value))
    onsets: list[tuple[int, float]] = []
    for candidate in candidates:
        if not onsets or candidate[0] - onsets[-1][0] >= minimum_onset_separation_ms:
            onsets.append(candidate)
        elif candidate[1] > onsets[-1][1]:
            onsets[-1] = candidate
    return AudioEventExtraction(tuple(intervals), tuple(timestamp for timestamp, _ in onsets))


def extract_audio_events_from_media(
    path: Path,
    *,
    active_start_ms: int,
    active_duration_ms: int,
) -> AudioEventExtraction:
    samples = decode_audio_segment(
        path,
        start_ms=active_start_ms,
        duration_ms=active_duration_ms,
    )
    return extract_energy_events(samples, sample_rate=16000)
