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
class SequenceEffect:
    """Progressive decrement across the tapping trial (MDS-UPDRS 3.4 hallmark).

    The cardinal parkinsonian sign is amplitude/velocity decrement over the
    sequence, distinct from mean rate. Slopes are per-tap; ratio is final-third
    over first-third mean amplitude (<1 means the movement shrank).
    """

    amplitude_decrement_slope: float | None
    amplitude_decrement_ratio: float | None
    speed_decrement_slope_ms: float | None
    halt_count: int | None


def _ols_slope(values: list[float]) -> float | None:
    """Least-squares slope of values against their integer index (0..n-1)."""
    n = len(values)
    if n < 2:
        return None
    mean_x = (n - 1) / 2.0
    mean_y = sum(values) / n
    var_x = sum((i - mean_x) ** 2 for i in range(n))
    if var_x == 0:
        return None
    covariance = sum((i - mean_x) * (value - mean_y) for i, value in enumerate(values))
    return covariance / var_x


def compute_sequence_effect(
    tap_times_ms: list[int],
    tap_amplitudes: list[float],
    *,
    halt_interval_multiple: float = 2.0,
) -> SequenceEffect:
    """Derive decrement features from ordered per-tap amplitudes and times.

    ``halt_count`` is the number of inter-tap intervals exceeding
    ``halt_interval_multiple`` times the median interval (hesitations/halts).
    Fields are None when too few taps exist to estimate them.
    """
    ordered = [amplitude for _, amplitude in sorted(zip(tap_times_ms, tap_amplitudes))]
    slope = _ols_slope(ordered)

    ratio: float | None = None
    if len(ordered) >= 3:
        third = len(ordered) // 3
        first_third = ordered[:third]
        final_third = ordered[-third:]
        first_mean = sum(first_third) / len(first_third)
        if first_mean > 0:
            ratio = (sum(final_third) / len(final_third)) / first_mean

    times = sorted(tap_times_ms)
    intervals = [later - earlier for earlier, later in zip(times, times[1:]) if later > earlier]
    speed_slope = _ols_slope([float(interval) for interval in intervals])
    halt_count: int | None = None
    if intervals:
        median_interval = median(intervals)
        halt_count = sum(1 for interval in intervals if interval > halt_interval_multiple * median_interval)

    return SequenceEffect(
        amplitude_decrement_slope=slope,
        amplitude_decrement_ratio=ratio,
        speed_decrement_slope_ms=speed_slope,
        halt_count=halt_count,
    )


@dataclass(frozen=True, slots=True)
class MeasurementResult:
    motor_events: tuple[TimestampedEvent, ...]
    speech_events: tuple[TimestampedEvent, ...]
    motor_rhythm: RhythmFeatures | None
    speech_rhythm: RhythmFeatures | None
    speech_timing: SpeechTimingFeatures | None
    median_motor_amplitude: float | None
    sequence_effect: SequenceEffect | None
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
    sequence_effect = compute_sequence_effect(tap_times, tap_amplitudes) if tap_times else None
    return MeasurementResult(
        motor_events=motor_events,
        speech_events=speech_events,
        motor_rhythm=motor_rhythm,
        speech_rhythm=speech_rhythm,
        speech_timing=speech_timing,
        median_motor_amplitude=median(tap_amplitudes) if tap_amplitudes else None,
        sequence_effect=sequence_effect,
        coupling=coupling,
    )
