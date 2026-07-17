from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True, slots=True)
class SpeechTimingFeatures:
    speech_onset_latency_ms: int | None
    voiced_duration_ms: int
    pause_percentage: float | None
    mean_pause_duration_ms: float | None
    maximum_pause_duration_ms: int | None


def merge_intervals(
    intervals: list[tuple[int, int]],
    *,
    lower_bound_ms: int,
    upper_bound_ms: int,
) -> list[tuple[int, int]]:
    """Clip, sort and merge overlapping or touching intervals."""
    if upper_bound_ms <= lower_bound_ms:
        raise ValueError("upper_bound_ms must exceed lower_bound_ms")
    clipped = sorted(
        (max(lower_bound_ms, start), min(upper_bound_ms, end))
        for start, end in intervals
        if end > start and min(upper_bound_ms, end) > max(lower_bound_ms, start)
    )
    merged: list[tuple[int, int]] = []
    for start, end in clipped:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
            continue
        previous_start, previous_end = merged[-1]
        merged[-1] = (previous_start, max(previous_end, end))
    return merged


def calculate_speech_timing_features(
    voiced_intervals: list[tuple[int, int]],
    *,
    active_duration_ms: int,
    analysis_pause_threshold_ms: int = 150,
) -> SpeechTimingFeatures:
    if active_duration_ms <= 0:
        raise ValueError("active_duration_ms must be positive")
    if analysis_pause_threshold_ms < 0:
        raise ValueError("analysis_pause_threshold_ms must be non-negative")

    cleaned = merge_intervals(
        voiced_intervals,
        lower_bound_ms=0,
        upper_bound_ms=active_duration_ms,
    )
    voiced_duration = sum(end - start for start, end in cleaned)
    pauses: list[int] = []
    previous_end = 0
    for start, end in cleaned:
        gap = start - previous_end
        if gap >= analysis_pause_threshold_ms:
            pauses.append(gap)
        previous_end = end
    trailing = active_duration_ms - previous_end
    if trailing >= analysis_pause_threshold_ms:
        pauses.append(trailing)
    onset = cleaned[0][0] if cleaned else None
    pause_total = sum(pauses)
    return SpeechTimingFeatures(
        speech_onset_latency_ms=onset,
        voiced_duration_ms=voiced_duration,
        pause_percentage=100.0 * pause_total / active_duration_ms,
        mean_pause_duration_ms=mean(pauses) if pauses else None,
        maximum_pause_duration_ms=max(pauses) if pauses else None,
    )
