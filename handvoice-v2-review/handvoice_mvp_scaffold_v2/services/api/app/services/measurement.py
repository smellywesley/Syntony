from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pipelines.audio.acoustic import extract_acoustic_features
from pipelines.audio.media import decode_audio_segment, extract_energy_events
from pipelines.common.contracts import Modality
from pipelines.dual_task.cost import Orientation, calculate_dual_task_cost, robust_condition_estimate
from pipelines.measurement.core import analyze_measurement
from pipelines.quality.confounds import CaptureConfounds, compute_capture_confounds
from pipelines.quality.decision import (
    QualityAssessment,
    QualityDecision,
    assess_capture_quality,
    compute_audio_quality,
)
from pipelines.video.contracts import FrameValidity, LandmarkFrame
from pipelines.video.extractor import derive_hand_signal
from services.api.app.models.entities import (
    AssessmentSession,
    Event,
    Feature,
    Recording,
    SessionStatus,
    TaskInstance,
    TaskStatus,
)
from services.api.app.schemas.api import MeasurementSubmission
from services.api.app.services.media import (
    MediaCleanupError,
    claim_uploaded_media,
    discard_pending_upload,
    discard_uploaded_media,
    resolve_storage_key,
    validate_uploaded_media,
)
from services.api.app.services.protocol import load_protocol

ALGORITHM_VERSION = "mvp-sync-0.2.0"
AUDIO_SAMPLE_RATE = 16000
MEASURED_QUALITY_KEYS = (
    "median_fps",
    "valid_frame_fraction",
    "out_of_guide_frame_fraction",
    "wrong_hand_frame_fraction",
    "audio_snr_db",
    "audio_clipping_fraction",
    "av_start_offset_ms",
    "motor_event_count",
    "ddk_event_count",
)


@dataclass(frozen=True, slots=True)
class MeasurementOutcome:
    assessment: QualityAssessment
    recording: Recording | None = None


def discard_unaccepted_media(db: Session, storage_key: str) -> bool:
    """Discard an upload only when no accepted recording references it."""
    path = resolve_storage_key(storage_key)
    referenced = db.scalar(
        select(Recording.id).where(Recording.object_uri == f"file://{path}")
    )
    return False if referenced is not None else discard_uploaded_media(storage_key)


def _accepted_assessment(db: Session, task_id: UUID) -> QualityAssessment:
    rows = db.execute(
        select(Feature.feature_name, Feature.value).where(
            Feature.task_instance_id == task_id,
            Feature.feature_name.in_(tuple(f"qc_{key}" for key in MEASURED_QUALITY_KEYS)),
        )
    ).all()
    measured = {key: None for key in MEASURED_QUALITY_KEYS}
    for feature_name, value in rows:
        measured[feature_name.removeprefix("qc_")] = value
    # Recordings accepted before the contract correctly return unknown values
    # rather than substituting nominal container metadata for measured QC.
    return QualityAssessment(QualityDecision.ACCEPT, (), measured, "quality.accepted")


def _discard_claimed_after_failure(db: Session, storage_key: str, cause: Exception | None = None) -> None:
    db.rollback()
    try:
        discard_unaccepted_media(db, storage_key)
    except MediaCleanupError as cleanup_error:
        if cause is not None:
            raise cleanup_error from cause
        raise


def _feature(
    task_id: UUID,
    modality: str,
    name: str,
    value: float | None,
    unit: str,
    *,
    status: str = "accepted",
    metadata: dict | None = None,
) -> Feature:
    return Feature(
        task_instance_id=task_id,
        modality=modality,
        feature_name=name,
        value=value,
        unit=unit,
        status=status,
        algorithm_version=ALGORITHM_VERSION,
        metadata_json=metadata or {},
    )


def _validate_task_payload(task: TaskInstance, payload: MeasurementSubmission) -> None:
    has_hand = bool(payload.landmark_frames)
    has_supplied_speech = bool(payload.ddk_event_ms or payload.voiced_intervals)
    if task.task_code == "T01":
        if not has_hand:
            raise ValueError("right-hand tapping requires landmark frames")
        if has_supplied_speech:
            raise ValueError("right-hand tapping does not accept speech annotations")
    elif task.task_code == "T02":
        if has_hand:
            raise ValueError("speech-only task does not accept hand landmark frames")
    elif task.task_code == "T03":
        if not has_hand:
            raise ValueError("dual task requires landmark frames")
    else:
        raise ValueError("unsupported task code")


def submit_measurement(
    db: Session,
    task: TaskInstance,
    payload: MeasurementSubmission,
) -> MeasurementOutcome:
    protocol = load_protocol()
    if task.status == TaskStatus.COMPLETE.value:
        existing = db.scalar(select(Recording).where(Recording.task_instance_id == task.id))
        if existing and existing.sha256 == payload.sha256.lower():
            discard_pending_upload(
                payload.storage_key,
                expected_sha256=payload.sha256,
            )
            return MeasurementOutcome(_accepted_assessment(db, task.id), existing)
        discard_pending_upload(payload.storage_key)
        raise ValueError("task already has an accepted recording; create a repeat task instead")
    if db.scalar(select(func.count(Recording.id)).where(Recording.task_instance_id == task.id)):
        discard_pending_upload(payload.storage_key)
        raise ValueError("task already has a registered recording")

    claimed = claim_uploaded_media(payload.storage_key)
    claimed_payload = payload.model_copy(update={"storage_key": claimed.storage_key})
    try:
        outcome = _process_claimed_measurement(db, task, claimed_payload, protocol)
    except Exception as exc:
        _discard_claimed_after_failure(db, claimed.storage_key, exc)
        raise
    if outcome.recording is None:
        _discard_claimed_after_failure(db, claimed.storage_key)
    return outcome


def _process_claimed_measurement(
    db: Session,
    task: TaskInstance,
    payload: MeasurementSubmission,
    protocol: dict[str, Any],
) -> MeasurementOutcome:
    if payload.capture_interrupted:
        assessment = assess_capture_quality(
            protocol=protocol,
            requires_hand=task.task_code in {"T01", "T03"},
            requires_speech=task.task_code in {"T02", "T03"},
            median_fps=None,
            valid_frame_fraction=None,
            out_of_guide_frame_fraction=None,
            audio=None,
            av_start_offset_ms=None,
            motor_event_count=0,
            ddk_event_count=0,
            capture_interrupted=True,
        )
        return MeasurementOutcome(assessment)

    _validate_task_payload(task, payload)
    media = validate_uploaded_media(
        payload.storage_key,
        payload.sha256,
        required_end_ms=payload.manifest.active_end_ms,
    )
    frames = [
        LandmarkFrame(
            timestamp_ms=frame.timestamp_ms,
            handedness=frame.handedness,
            landmarks_xyz=tuple(frame.landmarks_xyz),
            median_confidence=frame.median_confidence,
            validity=FrameValidity(frame.validity),
        )
        for frame in payload.landmark_frames
    ]
    hand_samples = derive_hand_signal(frames)
    voiced_intervals = [(interval.start_ms, interval.end_ms) for interval in payload.voiced_intervals]
    ddk_event_ms = list(payload.ddk_event_ms)
    acoustic = None
    audio_quality = None
    audio_decode_failed = False
    if task.task_code in {"T02", "T03"}:
        # Decode the active window once and reuse it for the energy-event
        # baseline (only when the client did not supply annotations) and for the
        # acoustic voice features, which always come from the raw waveform.
        try:
            samples = decode_audio_segment(
                media.path,
                start_ms=payload.manifest.active_start_ms,
                duration_ms=protocol["timing"]["active_ms"],
                sample_rate=AUDIO_SAMPLE_RATE,
            )
        except (ValueError, RuntimeError):
            samples = None
            audio_decode_failed = True
        if samples is not None:
            audio_quality = compute_audio_quality(samples)
            if not voiced_intervals or not ddk_event_ms:
                audio_events = extract_energy_events(samples, sample_rate=AUDIO_SAMPLE_RATE)
                if not voiced_intervals:
                    voiced_intervals = list(audio_events.voiced_intervals)
                if not ddk_event_ms:
                    ddk_event_ms = list(audio_events.onset_times_ms)
            acoustic = extract_acoustic_features(samples, sample_rate=AUDIO_SAMPLE_RATE)

    result = analyze_measurement(
        active_duration_ms=protocol["timing"]["active_ms"],
        hand_samples=hand_samples,
        voiced_intervals=voiced_intervals,
        ddk_event_ms=ddk_event_ms,
        coupling_window_ms=protocol["coupling"]["coincidence_window_ms"],
    )

    confounds = compute_capture_confounds(hand_samples) if frames else CaptureConfounds(None, None, None)
    handedness_frames = [
        frame
        for frame in payload.landmark_frames
        if frame.median_confidence >= 0.5 and frame.validity != FrameValidity.MISSING_HAND.value
    ]
    wrong_hand_frame_fraction = (
        sum(frame.handedness != "right" for frame in handedness_frames) / len(handedness_frames)
        if handedness_frames
        else None
    )
    achieved_fps = confounds.achieved_frame_rate_hz
    if achieved_fps is not None:
        achieved_fps = min(achieved_fps, media.video_fps)
    assessment = assess_capture_quality(
        protocol=protocol,
        requires_hand=task.task_code in {"T01", "T03"},
        requires_speech=task.task_code in {"T02", "T03"},
        median_fps=achieved_fps,
        valid_frame_fraction=confounds.valid_frame_fraction,
        out_of_guide_frame_fraction=(
            sum(frame.validity == FrameValidity.OUT_OF_GUIDE for frame in frames) / len(frames)
            if frames
            else None
        ),
        audio=audio_quality,
        av_start_offset_ms=float(abs(media.video_start_ms - media.audio_start_ms)),
        motor_event_count=0 if result.motor_rhythm is None else result.motor_rhythm.event_count,
        ddk_event_count=0 if result.speech_rhythm is None else result.speech_rhythm.event_count,
        audio_decode_failed=audio_decode_failed,
        wrong_hand_frame_fraction=(
            wrong_hand_frame_fraction if task.hand == "right" else None
        ),
    )
    if assessment.decision != QualityDecision.ACCEPT:
        return MeasurementOutcome(assessment)

    recording = Recording(
        task_instance_id=task.id,
        object_uri=f"file://{media.path}",
        sha256=payload.sha256.lower(),
        duration_ms=media.duration_ms,
        video_fps=media.video_fps,
        audio_sample_rate=media.audio_sample_rate,
    )
    db.add(recording)
    db.flush()

    for event in (*result.motor_events, *result.speech_events):
        event_metadata = dict(event.metadata)
        if event.modality == Modality.SPEECH:
            event_metadata.update({"status": "exploratory_unvalidated", "validated": False})
        db.add(
            Event(
                task_instance_id=task.id,
                modality=event.modality.value,
                event_type=event.event_type,
                start_ms=event.start_ms,
                end_ms=event.end_ms,
                confidence=event.confidence,
                value_json=event_metadata,
                algorithm_version=ALGORITHM_VERSION,
            )
        )

    if result.motor_rhythm:
        db.add_all(
            [
                _feature(task.id, Modality.MOTOR.value, "tap_rate_hz", result.motor_rhythm.rate_hz, "Hz"),
                _feature(task.id, Modality.MOTOR.value, "tap_interval_cv", result.motor_rhythm.interval_cv, "proportion"),
                _feature(task.id, Modality.MOTOR.value, "median_tap_amplitude", result.median_motor_amplitude, "normalized"),
                _feature(task.id, Modality.MOTOR.value, "tap_event_count", float(result.motor_rhythm.event_count), "count"),
            ]
        )
    if result.sequence_effect:
        sequence = result.sequence_effect
        db.add_all(
            [
                _feature(task.id, Modality.MOTOR.value, "amplitude_decrement_slope", sequence.amplitude_decrement_slope, "per_tap", status="exploratory_unvalidated"),
                _feature(task.id, Modality.MOTOR.value, "amplitude_decrement_ratio", sequence.amplitude_decrement_ratio, "proportion", status="exploratory_unvalidated"),
                _feature(task.id, Modality.MOTOR.value, "speed_decrement_slope", sequence.speed_decrement_slope_ms, "ms_per_interval", status="exploratory_unvalidated"),
                _feature(
                    task.id,
                    Modality.MOTOR.value,
                    "halt_count",
                    None if sequence.halt_count is None else float(sequence.halt_count),
                    "count",
                    status="exploratory_unvalidated",
                ),
            ]
        )
    if frames:
        db.add_all(
            [
                _feature(task.id, Modality.QUALITY.value, "achieved_frame_rate_hz", confounds.achieved_frame_rate_hz, "Hz", status="confound"),
                _feature(task.id, Modality.QUALITY.value, "valid_frame_fraction", confounds.valid_frame_fraction, "proportion", status="confound"),
                _feature(task.id, Modality.QUALITY.value, "median_palm_scale", confounds.median_palm_scale, "normalized", status="confound"),
            ]
        )
    quality_units = {
        "median_fps": "Hz",
        "valid_frame_fraction": "proportion",
        "out_of_guide_frame_fraction": "proportion",
        "wrong_hand_frame_fraction": "proportion",
        "audio_snr_db": "dB",
        "audio_clipping_fraction": "proportion",
        "av_start_offset_ms": "ms",
        "motor_event_count": "count",
        "ddk_event_count": "count",
    }
    db.add_all(
        [
            _feature(
                task.id,
                Modality.QUALITY.value,
                f"qc_{key}",
                assessment.measured_quality[key],
                quality_units[key],
                status="quality_contract",
                metadata={"contract_version": "1"},
            )
            for key in MEASURED_QUALITY_KEYS
        ]
    )
    if result.speech_rhythm:
        db.add_all(
            [
                _feature(task.id, Modality.SPEECH.value, "ddk_rate_hz", result.speech_rhythm.rate_hz, "Hz", status="exploratory_unvalidated"),
                _feature(task.id, Modality.SPEECH.value, "ddk_interval_cv", result.speech_rhythm.interval_cv, "proportion", status="exploratory_unvalidated"),
                _feature(task.id, Modality.SPEECH.value, "ddk_event_count", float(result.speech_rhythm.event_count), "count", status="exploratory_unvalidated"),
            ]
        )
    if result.ddk_dynamics:
        dynamics = result.ddk_dynamics
        db.add_all(
            [
                _feature(task.id, Modality.SPEECH.value, "ddk_ioi_mean_ms", dynamics.inter_onset_interval_mean_ms, "ms", status="exploratory_unvalidated"),
                _feature(task.id, Modality.SPEECH.value, "ddk_ioi_sd_ms", dynamics.inter_onset_interval_sd_ms, "ms", status="exploratory_unvalidated"),
                _feature(task.id, Modality.SPEECH.value, "ddk_rate_variance_hz2", dynamics.instantaneous_rate_variance_hz2, "Hz2", status="exploratory_unvalidated"),
                _feature(task.id, Modality.SPEECH.value, "ddk_dwell_time_mean_ms", dynamics.dwell_time_mean_ms, "ms", status="exploratory_unvalidated"),
                _feature(task.id, Modality.SPEECH.value, "ddk_dwell_time_sd_ms", dynamics.dwell_time_sd_ms, "ms", status="exploratory_unvalidated"),
                _feature(task.id, Modality.SPEECH.value, "ddk_rate_decrement_slope", dynamics.rate_decrement_slope_hz_per_syllable, "hz_per_syllable", status="exploratory_unvalidated"),
            ]
        )
    if result.speech_timing:
        db.add_all(
            [
                _feature(task.id, Modality.SPEECH.value, "voiced_duration_ms", float(result.speech_timing.voiced_duration_ms), "ms", status="exploratory_unvalidated"),
                _feature(task.id, Modality.SPEECH.value, "pause_percentage", result.speech_timing.pause_percentage, "percent", status="exploratory_unvalidated"),
            ]
        )
    if acoustic and acoustic.voiced_frame_count > 0:
        # Unvalidated acoustic baseline (autocorrelation pitch tracking); flagged
        # in metadata so it is never mistaken for a validated clinical measure.
        acoustic_meta = {"method": "autocorrelation_baseline", "validated": False}
        db.add_all(
            [
                _feature(task.id, Modality.SPEECH.value, "mean_f0_hz", acoustic.mean_f0_hz, "Hz", status="exploratory_unvalidated", metadata=acoustic_meta),
                _feature(task.id, Modality.SPEECH.value, "f0_std_hz", acoustic.f0_std_hz, "Hz", status="exploratory_unvalidated", metadata=acoustic_meta),
                _feature(task.id, Modality.SPEECH.value, "f0_range_hz", acoustic.f0_range_hz, "Hz", status="exploratory_unvalidated", metadata=acoustic_meta),
                _feature(task.id, Modality.SPEECH.value, "jitter_local_percent", acoustic.jitter_local_percent, "percent", status="exploratory_unvalidated", metadata=acoustic_meta),
                _feature(task.id, Modality.SPEECH.value, "shimmer_local_percent", acoustic.shimmer_local_percent, "percent", status="exploratory_unvalidated", metadata=acoustic_meta),
                _feature(task.id, Modality.SPEECH.value, "mean_hnr_db", acoustic.mean_hnr_db, "dB", status="exploratory_unvalidated", metadata=acoustic_meta),
                _feature(task.id, Modality.QUALITY.value, "voiced_fraction", acoustic.voiced_fraction, "proportion", status="confound"),
            ]
        )
    if result.coupling:
        db.add_all(
            [
                _feature(
                    task.id,
                    Modality.COUPLING.value,
                    "event_coincidence_rate",
                    result.coupling.event_coincidence_rate,
                    "proportion",
                    status="exploratory",
                    metadata={"matching": "maximum_cardinality_minimum_total_lag"},
                ),
                _feature(
                    task.id,
                    Modality.COUPLING.value,
                    "matched_event_count",
                    float(result.coupling.matched_count),
                    "count",
                    status="exploratory",
                ),
            ]
        )

    task.manifest_json = payload.manifest.model_dump()
    task.status = TaskStatus.COMPLETE.value
    session = db.get(AssessmentSession, task.session_id)
    if session:
        completed_codes = set(
            db.scalars(
                select(TaskInstance.task_code).where(
                    TaskInstance.session_id == session.id,
                    TaskInstance.repetition == 1,
                    TaskInstance.status == TaskStatus.COMPLETE.value,
                )
            ).all()
        )
        session.status = (
            SessionStatus.COMPLETE.value
            if completed_codes == {"T01", "T02", "T03"}
            else SessionStatus.CAPTURING.value
        )
    db.commit()
    db.refresh(recording)
    return MeasurementOutcome(assessment, recording)


def schedule_repeat(db: Session, task: TaskInstance) -> TaskInstance:
    protocol = load_protocol()
    if task.status != TaskStatus.COMPLETE.value:
        raise ValueError("repeat can only be created after an accepted first capture")
    if task.repetition >= int(protocol["max_repetitions"]):
        raise ValueError("maximum repetitions reached")
    existing = db.scalar(
        select(TaskInstance).where(
            TaskInstance.session_id == task.session_id,
            TaskInstance.task_code == task.task_code,
            TaskInstance.repetition == task.repetition + 1,
        )
    )
    if existing:
        return existing
    max_order = db.scalar(
        select(func.max(TaskInstance.order_index)).where(TaskInstance.session_id == task.session_id)
    )
    repeat = TaskInstance(
        session_id=task.session_id,
        task_code=task.task_code,
        task_name=task.task_name,
        condition=task.condition,
        hand=task.hand,
        speech_task=task.speech_task,
        repetition=task.repetition + 1,
        order_index=int(max_order or 0) + 1,
    )
    db.add(repeat)
    db.commit()
    db.refresh(repeat)
    return repeat


def _values(db: Session, session_id: UUID, task_code: str, feature_name: str) -> list[float | None]:
    return list(
        db.scalars(
            select(Feature.value)
            .join(TaskInstance, Feature.task_instance_id == TaskInstance.id)
            .where(
                TaskInstance.session_id == session_id,
                TaskInstance.task_code == task_code,
                Feature.feature_name == feature_name,
            )
        ).all()
    )


def session_metrics(db: Session, session_id: UUID) -> tuple[dict[str, float | None], dict[str, float | None]]:
    definitions = [
        ("motor_rate_dtc_percent", "tap_rate_hz", Orientation.HIGHER_IS_BETTER, "T01", "T03"),
        ("motor_rhythm_dtc_percent", "tap_interval_cv", Orientation.LOWER_IS_BETTER, "T01", "T03"),
        ("speech_rate_dtc_percent", "ddk_rate_hz", Orientation.HIGHER_IS_BETTER, "T02", "T03"),
        ("speech_rhythm_dtc_percent", "ddk_interval_cv", Orientation.LOWER_IS_BETTER, "T02", "T03"),
    ]
    metrics: dict[str, float | None] = {}
    for output_name, feature_name, orientation, single_code, dual_code in definitions:
        single = robust_condition_estimate(_values(db, session_id, single_code, feature_name))
        dual = robust_condition_estimate(_values(db, session_id, dual_code, feature_name))
        metrics[output_name] = calculate_dual_task_cost(single, dual, orientation).percent_cost

    coupling_values = _values(db, session_id, "T03", "event_coincidence_rate")
    coupling = {
        "event_coincidence_rate": robust_condition_estimate(coupling_values),
    }
    return metrics, coupling
