"""Tests for DDK temporal fine-structure features: inter-onset interval stats,
inter-syllable dwell time, instantaneous-rate variance, and the rate-decrement
slope (the speech analogue of the motor sequence effect)."""

from pipelines.measurement.core import compute_ddk_dynamics

ACTIVE_MS = 10000


def test_regular_cadence_has_flat_rate_and_zero_variance():
    onsets = list(range(200, 9800, 200))  # steady 5 Hz
    dynamics = compute_ddk_dynamics(onsets, [], active_duration_ms=ACTIVE_MS)

    assert dynamics.inter_onset_interval_mean_ms == 200
    assert dynamics.inter_onset_interval_sd_ms == 0
    assert dynamics.instantaneous_rate_variance_hz2 is not None
    assert dynamics.instantaneous_rate_variance_hz2 < 1e-9
    assert dynamics.rate_decrement_slope_hz_per_syllable is not None
    assert abs(dynamics.rate_decrement_slope_hz_per_syllable) < 1e-9


def test_slowing_cadence_has_negative_rate_slope():
    # Intervals grow over the trial -> instantaneous rate falls -> negative slope.
    onsets = [200]
    interval = 150
    while onsets[-1] + interval < ACTIVE_MS:
        onsets.append(onsets[-1] + interval)
        interval += 15
    dynamics = compute_ddk_dynamics(onsets, [], active_duration_ms=ACTIVE_MS)

    assert dynamics.rate_decrement_slope_hz_per_syllable is not None
    assert dynamics.rate_decrement_slope_hz_per_syllable < 0
    assert dynamics.instantaneous_rate_variance_hz2 is not None
    assert dynamics.instantaneous_rate_variance_hz2 > 0


def test_dwell_time_from_voiced_interval_gaps():
    # Three voiced syllables with 100 ms and 150 ms silent gaps between them.
    voiced = [(0, 300), (400, 700), (850, 1150)]
    dynamics = compute_ddk_dynamics([500, 1000], voiced, active_duration_ms=ACTIVE_MS)

    assert dynamics.dwell_time_mean_ms == 125  # mean of 100 and 150
    assert dynamics.dwell_time_sd_ms is not None and dynamics.dwell_time_sd_ms > 0


def test_too_few_onsets_yield_none_fields():
    dynamics = compute_ddk_dynamics([500], [], active_duration_ms=ACTIVE_MS)
    assert dynamics.inter_onset_interval_mean_ms is None
    assert dynamics.inter_onset_interval_sd_ms is None
    assert dynamics.instantaneous_rate_variance_hz2 is None
    assert dynamics.rate_decrement_slope_hz_per_syllable is None
    assert dynamics.dwell_time_mean_ms is None
