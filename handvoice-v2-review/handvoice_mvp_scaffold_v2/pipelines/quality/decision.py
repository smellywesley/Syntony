"""Deterministic capture-quality decisions for the frozen HandVoice protocol."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import log10
from typing import Any

import numpy as np


class QualityDecision(StrEnum):
    ACCEPT = "accept"
    RETRY = "retry"
    REVIEW_NEEDED = "review_needed"


class QualityReason(StrEnum):
    LOW_FRAME_RATE = "low_frame_rate"
    LOW_VALID_FRAME_FRACTION = "low_valid_frame_fraction"
    HAND_OUT_OF_GUIDE = "hand_out_of_guide"
    WRONG_HAND = "wrong_hand"
    LOW_AUDIO_SNR = "low_audio_snr"
    AUDIO_CLIPPING = "audio_clipping"
    AV_START_OFFSET = "av_start_offset"
    AUDIO_DECODE_FAILED = "audio_decode_failed"
    SPEECH_NOT_DETECTED = "speech_not_detected"
    INSUFFICIENT_MOTOR_EVENTS = "insufficient_motor_events"
    INSUFFICIENT_DDK_EVENTS = "insufficient_ddk_events"
    CAPTURE_INTERRUPTED = "capture_interrupted"


@dataclass(frozen=True, slots=True)
class AudioQualityMetrics:
    snr_db: float | None
    clipping_fraction: float | None
    speech_detected: bool


@dataclass(frozen=True, slots=True)
class QualityAssessment:
    decision: QualityDecision
    reason_codes: tuple[QualityReason, ...]
    measured_quality: dict[str, float | None]
    guidance_key: str


def compute_audio_quality(samples: np.ndarray) -> AudioQualityMetrics:
    """Return dependency-light signal-quality proxies from normalized PCM.

    SNR compares high-energy (speech) and low-energy (pause/background) frame
    RMS levels. It is a capture-quality estimate, not a clinical acoustic
    endpoint, and assumes the DDK recording contains short speech pauses.
    """
    values = np.asarray(samples, dtype=np.float64).reshape(-1)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return AudioQualityMetrics(None, None, False)

    absolute = np.abs(values)
    frame_size = min(320, values.size)  # 20 ms at the fixed 16 kHz decode rate.
    hop_size = max(1, frame_size // 2)
    starts = range(0, max(1, values.size - frame_size + 1), hop_size)
    frame_rms = np.asarray(
        [float(np.sqrt(np.mean(values[start : start + frame_size] ** 2))) for start in starts]
    )
    speech_rms = float(np.quantile(frame_rms, 0.80))
    noise_rms = float(np.quantile(frame_rms, 0.20))
    snr_db = (
        None
        if speech_rms <= 1e-8
        else 20.0 * log10(speech_rms / max(noise_rms, 1e-8))
    )
    clipping_fraction = float(np.mean(absolute >= 0.99))
    speech_detected = speech_rms >= 0.01 and snr_db is not None and snr_db >= 3.0
    return AudioQualityMetrics(snr_db, clipping_fraction, speech_detected)


def _lower_is_better(value: float | None, accept: float, reject: float) -> QualityDecision:
    if value is None or value >= reject:
        return QualityDecision.RETRY
    if value <= accept:
        return QualityDecision.ACCEPT
    return QualityDecision.REVIEW_NEEDED


def _higher_is_better(value: float | None, accept: float, reject: float) -> QualityDecision:
    if value is None or value <= reject:
        return QualityDecision.RETRY
    if value >= accept:
        return QualityDecision.ACCEPT
    return QualityDecision.REVIEW_NEEDED


def assess_capture_quality(
    *,
    protocol: dict[str, Any],
    requires_hand: bool,
    requires_speech: bool,
    median_fps: float | None,
    valid_frame_fraction: float | None,
    out_of_guide_frame_fraction: float | None,
    audio: AudioQualityMetrics | None,
    av_start_offset_ms: float | None,
    motor_event_count: int,
    ddk_event_count: int,
    audio_decode_failed: bool = False,
    capture_interrupted: bool = False,
    wrong_hand_frame_fraction: float | None = None,
) -> QualityAssessment:
    """Apply frozen thresholds and return one stable, auditable decision."""
    measured: dict[str, float | None] = {
        "median_fps": median_fps,
        "valid_frame_fraction": valid_frame_fraction,
        "out_of_guide_frame_fraction": out_of_guide_frame_fraction,
        "wrong_hand_frame_fraction": wrong_hand_frame_fraction,
        "audio_snr_db": None if audio is None else audio.snr_db,
        "audio_clipping_fraction": None if audio is None else audio.clipping_fraction,
        "av_start_offset_ms": av_start_offset_ms,
        "motor_event_count": float(motor_event_count),
        "ddk_event_count": float(ddk_event_count),
    }
    if capture_interrupted:
        return QualityAssessment(
            QualityDecision.RETRY,
            (QualityReason.CAPTURE_INTERRUPTED,),
            measured,
            "quality.retry.capture_interrupted",
        )

    defaults = protocol["quality_defaults"]
    checks: list[tuple[QualityReason, QualityDecision]] = []
    if requires_hand:
        video = defaults["video"]
        checks.extend(
            [
                (
                    QualityReason.LOW_FRAME_RATE,
                    _higher_is_better(
                        median_fps,
                        float(video["accept_median_fps"]),
                        float(video["reject_median_fps"]),
                    ),
                ),
                (
                    QualityReason.LOW_VALID_FRAME_FRACTION,
                    _higher_is_better(
                        valid_frame_fraction,
                        float(video["accept_valid_frame_fraction"]),
                        float(video["reject_valid_frame_fraction"]),
                    ),
                ),
            ]
        )
        if wrong_hand_frame_fraction is not None:
            checks.append(
                (
                    QualityReason.WRONG_HAND,
                    _lower_is_better(
                        wrong_hand_frame_fraction,
                        float(video["accept_wrong_hand_fraction"]),
                        float(video["reject_wrong_hand_fraction"]),
                    ),
                )
            )

    if requires_speech:
        audio_thresholds = defaults["audio"]
        if audio_decode_failed:
            checks.append((QualityReason.AUDIO_DECODE_FAILED, QualityDecision.RETRY))
        else:
            checks.extend(
                [
                    (
                        QualityReason.LOW_AUDIO_SNR,
                        _higher_is_better(
                            None if audio is None else audio.snr_db,
                            float(audio_thresholds["accept_snr_db"]),
                            float(audio_thresholds["reject_snr_db"]),
                        ),
                    ),
                    (
                        QualityReason.AUDIO_CLIPPING,
                        _lower_is_better(
                            None if audio is None else audio.clipping_fraction,
                            float(audio_thresholds["accept_clipping_fraction"]),
                            float(audio_thresholds["reject_clipping_fraction"]),
                        ),
                    ),
                ]
            )
            if audio is None or not audio.speech_detected:
                checks.append((QualityReason.SPEECH_NOT_DETECTED, QualityDecision.RETRY))

    synchronization = defaults["synchronization"]
    checks.append(
        (
            QualityReason.AV_START_OFFSET,
            _lower_is_better(
                av_start_offset_ms,
                float(synchronization["accept_start_offset_ms"]),
                float(synchronization["reject_start_offset_ms"]),
            ),
        )
    )
    if requires_hand and motor_event_count < 3:
        checks.append((QualityReason.INSUFFICIENT_MOTOR_EVENTS, QualityDecision.REVIEW_NEEDED))
    if requires_speech and ddk_event_count < 5:
        checks.append((QualityReason.INSUFFICIENT_DDK_EVENTS, QualityDecision.REVIEW_NEEDED))

    failures = [(reason, state) for reason, state in checks if state != QualityDecision.ACCEPT]
    valid_fraction_state = next(
        (state for reason, state in failures if reason == QualityReason.LOW_VALID_FRAME_FRACTION),
        None,
    )
    if out_of_guide_frame_fraction and valid_fraction_state is not None:
        failures.append((QualityReason.HAND_OUT_OF_GUIDE, valid_fraction_state))
    if any(state == QualityDecision.RETRY for _, state in failures):
        decision = QualityDecision.RETRY
    elif failures:
        decision = QualityDecision.REVIEW_NEEDED
    else:
        decision = QualityDecision.ACCEPT
    reasons = tuple(dict.fromkeys(reason for reason, _ in failures))
    guidance = (
        "quality.accepted"
        if not reasons
        else f"quality.{decision.value}.{reasons[0].value}"
    )
    return QualityAssessment(decision, reasons, measured, guidance)
