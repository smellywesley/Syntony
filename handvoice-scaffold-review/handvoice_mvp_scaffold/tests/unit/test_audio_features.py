from pipelines.audio.extractor import calculate_speech_timing_features


def test_pause_timing_features():
    result = calculate_speech_timing_features([(200, 1000), (1300, 2000), (2500, 3000)], active_duration_ms=4000)
    assert result.speech_onset_latency_ms == 200
    assert result.voiced_duration_ms == 2000
    assert result.maximum_pause_duration_ms == 1000
    assert result.pause_percentage == 50.0
