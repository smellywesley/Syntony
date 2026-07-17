from pipelines.audio.extractor import calculate_speech_timing_features, merge_intervals


def test_pause_timing_features():
    result = calculate_speech_timing_features(
        [(200, 1000), (1300, 2000), (2500, 3000)], active_duration_ms=4000
    )
    assert result.speech_onset_latency_ms == 200
    assert result.voiced_duration_ms == 2000
    assert result.maximum_pause_duration_ms == 1000
    assert result.pause_percentage == 50.0


def test_overlapping_voice_intervals_are_merged_before_features():
    result = calculate_speech_timing_features(
        [(100, 600), (500, 900), (850, 1100)], active_duration_ms=1500
    )
    assert merge_intervals(
        [(100, 600), (500, 900), (850, 1100)], lower_bound_ms=0, upper_bound_ms=1500
    ) == [(100, 1100)]
    assert result.voiced_duration_ms == 1000
    assert result.pause_percentage == 100.0 * 400 / 1500
    assert result.maximum_pause_duration_ms == 400


def test_intervals_are_clipped_to_active_window():
    result = calculate_speech_timing_features(
        [(-100, 200), (900, 1200)], active_duration_ms=1000
    )
    assert result.voiced_duration_ms == 300
