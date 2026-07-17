import pytest

from pipelines.audio.ddk_agreement import score_onset_agreement


def test_perfect_match_gives_f1_one_zero_error():
    onsets = [200, 400, 600, 800, 1000]
    result = score_onset_agreement(onsets, list(onsets), tolerance_ms=20)
    assert result.f1 == 1.0
    assert result.timing_mae_ms == 0.0


def test_miss_and_false_alarm_lower_precision_and_recall():
    reference = [200, 400, 600, 800, 1000]
    detected = [205, 410, 590, 1300]  # 800 missed, 1300 false alarm
    result = score_onset_agreement(reference, detected, tolerance_ms=20)
    assert result.matched_count == 3
    assert abs(result.precision - 3 / 4) < 1e-9
    assert abs(result.recall - 3 / 5) < 1e-9
    assert result.timing_mae_ms <= 20


def test_onset_outside_tolerance_is_not_matched():
    result = score_onset_agreement([200], [250], tolerance_ms=20)
    assert result.matched_count == 0
    assert result.f1 == 0.0


def test_one_detected_onset_cannot_validate_two_references():
    # two references 10 ms apart, one detected onset between them, tolerance 20
    result = score_onset_agreement([200, 220], [210], tolerance_ms=20)
    assert result.matched_count == 1


def test_negative_tolerance_is_rejected():
    with pytest.raises(ValueError):
        score_onset_agreement([100], [100], tolerance_ms=-1)
