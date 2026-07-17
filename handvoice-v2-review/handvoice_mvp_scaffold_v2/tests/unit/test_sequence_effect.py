from pipelines.measurement.core import compute_sequence_effect


def test_decrementing_amplitude_yields_negative_slope_and_ratio_below_one():
    amps = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]
    times = [0, 500, 1050, 1650, 2300, 3000]
    se = compute_sequence_effect(times, amps)
    assert se.amplitude_decrement_slope < 0
    assert se.amplitude_decrement_ratio < 1.0
    assert se.speed_decrement_slope_ms > 0  # intervals widen -> slowing


def test_flat_series_has_zero_slope_and_unit_ratio():
    se = compute_sequence_effect([0, 500, 1000, 1500, 2000, 2500], [0.8] * 6)
    assert abs(se.amplitude_decrement_slope) < 1e-9
    assert abs(se.amplitude_decrement_ratio - 1.0) < 1e-9


def test_halt_is_counted_when_interval_exceeds_twice_median():
    # steady 400 ms taps then one 1500 ms hesitation
    times = [0, 400, 800, 1200, 2700, 3100]
    se = compute_sequence_effect(times, [0.8] * 6)
    assert se.halt_count == 1


def test_sequence_effect_is_order_invariant():
    times = [0, 400, 800, 1200]
    amps = [1.0, 0.8, 0.6, 0.4]
    forward = compute_sequence_effect(times, amps)
    reversed_ = compute_sequence_effect(list(reversed(times)), list(reversed(amps)))
    assert forward == reversed_


def test_too_few_taps_leave_fields_none():
    se = compute_sequence_effect([100], [0.5])
    assert se.amplitude_decrement_slope is None
    assert se.amplitude_decrement_ratio is None
