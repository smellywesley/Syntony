"""Per-capture confound metrics logged so later analysis can regress them out.

Method anchor: monocular MediaPipe tapping amplitude scales with hand-to-camera
distance, and landmark accuracy degrades with motion blur at low frame rates;
validity work samples at 30/60/120 fps and treats sub-30 fps as a limitation
(Sensors 2022, MDPI 22:7992; MediaPipe-vs-standard, PMC11683656). Finger tapping
in Parkinson's reaches 3-6 Hz, so the ~15 fps effective capture rate is a real
Nyquist ceiling worth recording alongside every measurement.

NOTE: a rest-tremor proxy is intentionally NOT computed here. The frozen
protocol captures landmarks only inside the active task window, so there is no
rest-hold segment to estimate resting instability from. That proxy needs a
protocol change (a rest-hold capture) and is deferred to the clinician review.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from pipelines.video.extractor import HandSignalSample


@dataclass(frozen=True, slots=True)
class CaptureConfounds:
    achieved_frame_rate_hz: float | None
    valid_frame_fraction: float | None
    median_palm_scale: float | None


def compute_capture_confounds(samples: list[HandSignalSample]) -> CaptureConfounds:
    """Derive frame-rate, validity, and hand-distance confounds from samples.

    One sample exists per submitted frame (valid or not). Frame rate comes from
    the timestamp span; palm scale is available only on valid frames.
    """
    if not samples:
        return CaptureConfounds(None, None, None)

    timestamps = sorted(sample.timestamp_ms for sample in samples)
    span_ms = timestamps[-1] - timestamps[0]
    frame_rate = (len(timestamps) - 1) * 1000.0 / span_ms if span_ms > 0 else None

    valid_fraction = sum(1 for sample in samples if sample.valid) / len(samples)
    palm_scales = [sample.palm_scale for sample in samples if sample.palm_scale is not None]
    median_palm = median(palm_scales) if palm_scales else None

    return CaptureConfounds(
        achieved_frame_rate_hz=frame_rate,
        valid_frame_fraction=valid_fraction,
        median_palm_scale=median_palm,
    )


def demo() -> None:
    """Self-check: ~15 fps with one invalid frame and known palm scales."""
    samples = [
        HandSignalSample(t, None, 0.5, valid=(t != 132), palm_scale=(0.2 if t != 132 else None))
        for t in range(0, 1000, 66)
    ]
    confounds = compute_capture_confounds(samples)
    assert confounds.achieved_frame_rate_hz is not None
    assert 14 < confounds.achieved_frame_rate_hz < 16, confounds.achieved_frame_rate_hz
    assert confounds.valid_frame_fraction is not None and confounds.valid_frame_fraction < 1.0
    assert confounds.median_palm_scale == 0.2
    print(
        f"fps={confounds.achieved_frame_rate_hz:.1f} "
        f"valid={confounds.valid_frame_fraction:.2f} palm={confounds.median_palm_scale}"
    )


if __name__ == "__main__":
    demo()
