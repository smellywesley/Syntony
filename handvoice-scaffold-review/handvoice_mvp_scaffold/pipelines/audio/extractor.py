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


def calculate_speech_timing_features(
    voiced_intervals: list[tuple[int, int]],
    *,
    active_duration_ms: int,
    analysis_pause_threshold_ms: int = 150,
) -> SpeechTimingFeatures:
    if active_duration_ms <= 0:
        raise ValueError("active_duration_ms must be positive")
    cleaned = sorted((max(0, start), min(active_duration_ms, end)) for start, end in voiced_intervals if end > start)
    voiced_duration = sum(end - start for start, end in cleaned)
    pauses: list[int] = []
    previous_end = 0
    for start, end in cleaned:
        gap = start - previous_end
        if gap >= analysis_pause_threshold_ms:
            pauses.append(gap)
        previous_end = max(previous_end, end)
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
