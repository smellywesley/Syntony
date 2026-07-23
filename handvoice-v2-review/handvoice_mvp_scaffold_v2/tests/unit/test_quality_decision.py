from copy import deepcopy

import numpy as np
import pytest

from pipelines.quality.decision import (
    AudioQualityMetrics,
    QualityDecision,
    QualityReason,
    assess_capture_quality,
    compute_audio_quality,
)
from services.api.app.services.protocol import load_protocol


def _assessment(**overrides):
    values = {
        "protocol": deepcopy(load_protocol("configs/protocol.v1.yaml")),
        "requires_hand": True,
        "requires_speech": True,
        "median_fps": 30.0,
        "valid_frame_fraction": 0.95,
        "out_of_guide_frame_fraction": 0.0,
        "audio": AudioQualityMetrics(20.0, 0.0, True),
        "av_start_offset_ms": 0.0,
        "motor_event_count": 10,
        "ddk_event_count": 10,
        "wrong_hand_frame_fraction": 0.0,
    }
    values.update(overrides)
    return assess_capture_quality(**values)


def test_all_accept_thresholds_are_inclusive():
    result = _assessment(
        median_fps=24.0,
        valid_frame_fraction=0.85,
        audio=AudioQualityMetrics(15.0, 0.005, True),
        av_start_offset_ms=50.0,
    )
    assert result.decision == QualityDecision.ACCEPT
    assert result.reason_codes == ()
    assert result.guidance_key == "quality.accepted"


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"median_fps": 22.0}, QualityReason.LOW_FRAME_RATE),
        ({"valid_frame_fraction": 0.80}, QualityReason.LOW_VALID_FRAME_FRACTION),
        ({"audio": AudioQualityMetrics(12.0, 0.0, True)}, QualityReason.LOW_AUDIO_SNR),
        ({"audio": AudioQualityMetrics(20.0, 0.01, True)}, QualityReason.AUDIO_CLIPPING),
        ({"av_start_offset_ms": 75.0}, QualityReason.AV_START_OFFSET),
    ],
)
def test_between_accept_and_reject_threshold_requires_review(overrides, reason):
    result = _assessment(**overrides)
    assert result.decision == QualityDecision.REVIEW_NEEDED
    assert result.reason_codes == (reason,)
    assert result.guidance_key == f"quality.review_needed.{reason.value}"


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"median_fps": 20.0}, QualityReason.LOW_FRAME_RATE),
        ({"valid_frame_fraction": 0.70}, QualityReason.LOW_VALID_FRAME_FRACTION),
        ({"audio": AudioQualityMetrics(10.0, 0.0, True)}, QualityReason.LOW_AUDIO_SNR),
        ({"audio": AudioQualityMetrics(20.0, 0.02, True)}, QualityReason.AUDIO_CLIPPING),
        ({"av_start_offset_ms": 100.0}, QualityReason.AV_START_OFFSET),
        ({"audio_decode_failed": True}, QualityReason.AUDIO_DECODE_FAILED),
        ({"audio": AudioQualityMetrics(20.0, 0.0, False)}, QualityReason.SPEECH_NOT_DETECTED),
        ({"wrong_hand_frame_fraction": 0.20}, QualityReason.WRONG_HAND),
        ({"capture_interrupted": True}, QualityReason.CAPTURE_INTERRUPTED),
    ],
)
def test_reject_boundaries_and_hard_failures_require_retry(overrides, reason):
    result = _assessment(**overrides)
    assert result.decision == QualityDecision.RETRY
    assert reason in result.reason_codes


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"motor_event_count": 2}, QualityReason.INSUFFICIENT_MOTOR_EVENTS),
        ({"ddk_event_count": 4}, QualityReason.INSUFFICIENT_DDK_EVENTS),
    ],
)
def test_limited_task_performance_requires_review_not_forced_retry(overrides, reason):
    result = _assessment(**overrides)
    assert result.decision == QualityDecision.REVIEW_NEEDED
    assert result.reason_codes == (reason,)


def test_wrong_hand_consensus_uses_review_band_and_ignores_one_flicker():
    one_of_thirty = _assessment(wrong_hand_frame_fraction=1 / 30)
    review = _assessment(wrong_hand_frame_fraction=0.10)
    assert one_of_thirty.decision == QualityDecision.ACCEPT
    assert review.decision == QualityDecision.REVIEW_NEEDED
    assert review.reason_codes == (QualityReason.WRONG_HAND,)


def test_out_of_guide_is_reported_when_video_quality_fails():
    result = _assessment(valid_frame_fraction=0.70, out_of_guide_frame_fraction=0.4)
    assert result.reason_codes == (
        QualityReason.LOW_VALID_FRAME_FRACTION,
        QualityReason.HAND_OUT_OF_GUIDE,
    )


def test_out_of_guide_is_not_blame_when_only_audio_quality_fails():
    result = _assessment(
        audio=AudioQualityMetrics(10.0, 0.0, True),
        out_of_guide_frame_fraction=0.01,
    )
    assert result.reason_codes == (QualityReason.LOW_AUDIO_SNR,)


def test_audio_decode_and_missing_events_remain_distinct_reasons():
    result = _assessment(audio_decode_failed=True, ddk_event_count=0)
    assert result.reason_codes == (
        QualityReason.AUDIO_DECODE_FAILED,
        QualityReason.INSUFFICIENT_DDK_EVENTS,
    )


def test_modalities_only_apply_their_required_checks():
    hand_only = _assessment(requires_speech=False, audio=None, ddk_event_count=0)
    speech_only = _assessment(
        requires_hand=False,
        median_fps=None,
        valid_frame_fraction=None,
        motor_event_count=0,
    )
    assert hand_only.decision == QualityDecision.ACCEPT
    assert speech_only.decision == QualityDecision.ACCEPT


def test_audio_quality_distinguishes_silence_clean_signal_and_clipping():
    silence = compute_audio_quality(np.zeros(16000))
    assert silence.speech_detected is False
    assert silence.snr_db is None
    assert silence.clipping_fraction == 0.0

    sample_rate = 16000
    time_s = np.arange(sample_rate) / sample_rate
    carrier = 0.2 * np.sin(2 * np.pi * 220 * time_s)
    pulsed_speech = carrier * ((time_s % 0.30) < 0.16)
    clean = compute_audio_quality(pulsed_speech)
    assert clean.speech_detected is True
    assert clean.snr_db is not None and clean.snr_db > 15.0
    assert clean.clipping_fraction == 0.0

    rng = np.random.default_rng(7)
    moderate_noise = compute_audio_quality(pulsed_speech + rng.normal(0.0, 0.02, sample_rate))
    heavy_noise = compute_audio_quality(pulsed_speech + rng.normal(0.0, 0.08, sample_rate))
    assert moderate_noise.snr_db is not None
    assert heavy_noise.snr_db is not None
    assert clean.snr_db > moderate_noise.snr_db > heavy_noise.snr_db
    assert moderate_noise.snr_db >= 15.0
    assert heavy_noise.snr_db <= 10.0

    clipped = compute_audio_quality(np.ones(16000))
    assert clipped.clipping_fraction == 1.0
