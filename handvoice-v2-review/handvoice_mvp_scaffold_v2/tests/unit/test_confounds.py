from pipelines.quality.confounds import compute_capture_confounds
from pipelines.video.extractor import HandSignalSample


def _sample(t: int, *, valid: bool = True, palm: float | None = 0.2) -> HandSignalSample:
    return HandSignalSample(t, None, 0.5 if valid else None, valid, palm_scale=palm if valid else None)


def test_frame_rate_recovered_from_timestamps():
    samples = [_sample(t) for t in range(0, 1000, 66)]  # ~15 fps
    confounds = compute_capture_confounds(samples)
    assert 14 < confounds.achieved_frame_rate_hz < 16


def test_valid_fraction_and_palm_scale():
    samples = [_sample(0), _sample(66, valid=False), _sample(132), _sample(198)]
    confounds = compute_capture_confounds(samples)
    assert confounds.valid_frame_fraction == 0.75
    assert confounds.median_palm_scale == 0.2


def test_empty_samples_return_none():
    confounds = compute_capture_confounds([])
    assert confounds.achieved_frame_rate_hz is None
    assert confounds.valid_frame_fraction is None
    assert confounds.median_palm_scale is None
