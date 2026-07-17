from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import mean, median, pstdev

from pipelines.audio.extractor import SpeechTimingFeatures, calculate_speech_timing_features
from pipelines.common.contracts import Modality, TimestampedEvent
from pipelines.coupling.events import CouplingResult, calculate_event_coupling
from pipelines.video.extractor import HandSignalSample


@dataclass(frozen=True, slots=True)
class RhythmFeatures:
    event_count: int
    rate_hz: float
    interval_median_ms: float | None
    interval_cv: float | None


@dataclass(frozen=True, slots=True)
class MeasurementResult:
    motor_events: tuple[TimestampedEvent, ...]
    speech_events: tuple[TimestampedEvent, ...]
    motor_rhythm: RhythmFeatures | None
    speech_rhythm: RhythmFeatures | None
    speech_timing: SpeechTimingFeatures | None
    median_motor_amplitude: float | None
    coupling: CouplingResult | None


def calculate_rhythm_features(event_times_ms: list[int], *, active_duration_ms: int) -> RhythmFeatures:
    if active_duration_ms <= 0:
        raise ValueError("active_duration_ms must be positive")
    ordered = sorted(set(time for time in event_times_ms if 0 <= time <= active_duration_ms))
    intervals = [later - earlier for earlier, later in zip(ordered, ordered[1:]) if later > earlier]
    interval_mean = mean(intervals) if intervals else None
    interval_cv = (
        pstdev(intervals) / interval_mean
        if len(intervals) >= 2 and interval_mean is not None and interval_mean > 0
        else None
    )
    return RhythmFeatures(
        event_count=len(ordered),
        rate_hz=len(ordered) / (active_duration_ms / 1000.0),
        interval_median_ms=median(intervals) if intervals else None,
        interval_cv=interval_cv,
    )


def detect_tap_events(
    samples: list[HandSignalSample],
    *,
    minimum_separation_ms: int = 120,
) -> tuple[list[int], list[float]]:
    values_by_timestamp: dict[int, float] = {}
    for sample in samples:
        value = sample.normalized_thumb_index_distance
        if (
            sample.valid
            and value is not None
            and isfinite(value)
            and (
                sample.timestamp_ms not in values_by_timestamp
                or value > values_by_timestamp[sample.timestamp_ms]
            )
        ):
            values_by_timestamp[sample.timestamp_ms] = value
    valid = sorted(
        values_by_timestamp.items(),
        key=lambda item: item[0],
    )
    if len(valid) < 3:
        return [], []
    values = sorted(value for _, value in valid)
    low = values[max(0, round(0.1 * (len(values) - 1)))]
    high = values[min(len(values) - 1, round(0.9 * (len(values) - 1)))]
    if high - low <= 1e-6:
        return [], []
    threshold = low + 0.45 * (high - low)

    candidates: list[tuple[int, float]] = []
    for index in range(1, len(valid) - 1):
        timestamp, value = valid[index]
        previous_value = valid[index - 1][1]
        next_value = valid[index + 1][1]
        if value >= threshold and value > previous_value and value >= next_value:
            candidates.append((timestamp, value))

    selected: list[tuple[int, float]] = []
    for candidate in candidates:
        if not selected or candidate[0] - selected[-1][0] >= minimum_separation_ms:
            selected.append(candidate)
        elif candidate[1] > selected[-1][1]:
            selected[-1] = candidate
    return [timestamp for timestamp, _ in selected], [value for _, value in selected]


def analyze_measurement(
    *,
    active_duration_ms: int,
    hand_samples: list[HandSignalSample],
    voiced_intervals: list[tuple[int, int]],
    ddk_event_ms: list[int],
    coupling_window_ms: int,
) -> MeasurementResult:
    tap_times, tap_amplitudes = detect_tap_events(hand_samples)
    motor_events = tuple(
        TimestampedEvent(
            event_id=f"motor-{index}",
            modality=Modality.MOTOR,
            event_type="tap_opening",
            start_ms=timestamp,
            metadata={"amplitude": tap_amplitudes[index]},
        )
        for index, timestamp in enumerate(tap_times)
    )
    speech_times = sorted(set(time for time in ddk_event_ms if 0 <= time <= active_duration_ms))
    speech_events = tuple(
        TimestampedEvent(
            event_id=f"speech-{index}",
            modality=Modality.SPEECH,
            event_type="ddk_syllable_onset",
            start_ms=timestamp,
        )
        for index, timestamp in enumerate(speech_times)
    )
    motor_rhythm = calculate_rhythm_features(tap_times, active_duration_ms=active_duration_ms) if hand_samples else None
    speech_rhythm = calculate_rhythm_features(speech_times, active_duration_ms=active_duration_ms) if ddk_event_ms else None
    speech_timing = (
        calculate_speech_timing_features(voiced_intervals, active_duration_ms=active_duration_ms)
        if voiced_intervals
        else None
    )
    coupling = (
        calculate_event_coupling(motor_events, speech_events, window_ms=coupling_window_ms)
        if motor_events and speech_events
        else None
    )
    return MeasurementResult(
        motor_events=motor_events,
        speech_events=speech_events,
        motor_rhythm=motor_rhythm,
        speech_rhythm=speech_rhythm,
        speech_timing=speech_timing,
        median_motor_amplitude=median(tap_amplitudes) if tap_amplitudes else None,
        coupling=coupling,
    )
