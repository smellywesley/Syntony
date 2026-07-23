"""Trainable temporal motor-event detector layered on computer-vision tracking.

MediaPipe remains responsible for finding and tracking the hand. This module
only interprets the resulting normalized landmark time series. Model artifacts
are JSON data (never pickle) and release loading fails closed unless the
artifact records human annotation, participant-grouped evaluation, and the
frozen motor agreement gate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from itertools import combinations
import json
from math import isfinite, pi
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol, Sequence

import numpy as np
from jsonschema import Draft202012Validator

from pipelines.common.contracts import Modality
from pipelines.validation.agreement import (
    FROZEN_THRESHOLDS,
    EventAgreement,
    score_event_agreement,
)
from pipelines.video.contracts import FrameValidity, LandmarkFrame
from pipelines.video.extractor import (
    MINIMUM_TRACKING_CONFIDENCE,
    HandSignalSample,
    derive_hand_signal,
)


FEATURE_NAMES = (
    "distance_level",
    "angle_normalized",
    "rising_velocity",
    "falling_velocity",
    "peak_prominence",
    "tracking_confidence",
    "local_valid_fraction",
    "neighbor_gap_fraction",
)
ARTIFACT_SCHEMA_VERSION = "1.0"
MODEL_TYPE = "temporal_logistic"
LABEL_TOLERANCE_MS = 50
MINIMUM_SEPARATION_MS = 120
MAX_ARTIFACT_BYTES = 1_000_000
MAX_LANDMARK_FILE_BYTES = 25_000_000
TRAINING_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "validation"
    / "schemas"
    / "motor_training_manifest.v1.schema.json"
)


@dataclass(frozen=True, slots=True)
class MotorModelProvenance:
    dataset_id: str
    dataset_doi: str
    dataset_license: str
    dataset_kind: Literal["human_recordings", "synthetic_development"]
    annotation_profile: str
    human_annotated: bool
    annotators_blinded_to_detector: bool
    participant_grouped_split: bool
    training_manifest_sha256: str | None = None
    software_revision: str | None = None
    working_tree_dirty: bool | None = None


@dataclass(frozen=True, slots=True)
class MotorTrainingCase:
    case_id: str
    participant_id: str
    split: Literal["train", "validation", "test"]
    samples: tuple[HandSignalSample, ...]
    consensus_events_ms: tuple[int, ...]
    strata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MotorEventDetection:
    timestamps_ms: tuple[int, ...]
    amplitudes: tuple[float, ...]
    confidences: tuple[float, ...]
    detector_kind: str
    algorithm_version: str
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        length = len(self.timestamps_ms)
        if len(self.amplitudes) != length or len(self.confidences) != length:
            raise ValueError("motor detection timestamps, amplitudes, and confidences must align")
        if tuple(sorted(set(self.timestamps_ms))) != self.timestamps_ms:
            raise ValueError("motor detection timestamps must be sorted and unique")
        if any(timestamp < 0 for timestamp in self.timestamps_ms):
            raise ValueError("motor detection timestamps must be non-negative")
        if any(not isfinite(value) for value in self.amplitudes):
            raise ValueError("motor detection amplitudes must be finite")
        if any(not isfinite(value) or not 0 <= value <= 1 for value in self.confidences):
            raise ValueError("motor detection confidences must be between zero and one")


class MotorEventDetector(Protocol):
    def detect(self, samples: Sequence[HandSignalSample]) -> MotorEventDetection: ...


@dataclass(frozen=True, slots=True)
class _TemporalRows:
    timestamps_ms: np.ndarray
    features: np.ndarray
    amplitudes: np.ndarray
    local_valid_fraction: np.ndarray


def _validated_json(path: Path, *, maximum_bytes: int, label: str) -> Any:
    resolved = path.resolve(strict=True)
    if resolved.stat().st_size > maximum_bytes:
        raise ValueError(f"{label} exceeds the safe size limit")
    try:
        return json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} is not valid JSON") from error


def _contained_file(data_root: Path, relative_path: str) -> Path:
    root = data_root.resolve(strict=True)
    candidate = (root / relative_path).resolve(strict=True)
    if not candidate.is_relative_to(root):
        raise ValueError("landmark file escapes the configured data root")
    return candidate


def _landmark_frames(path: Path, *, case_id: str, expected_sha256: str) -> list[LandmarkFrame]:
    raw = path.read_bytes()
    if len(raw) > MAX_LANDMARK_FILE_BYTES:
        raise ValueError(f"landmark file for {case_id} exceeds the safe size limit")
    if sha256(raw).hexdigest().lower() != expected_sha256.lower():
        raise ValueError(f"landmark SHA-256 mismatch for {case_id}")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"landmark file for {case_id} is not valid JSON") from error
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "case_id", "frames"}:
        raise ValueError(f"landmark file for {case_id} has an invalid contract")
    if payload["schema_version"] != "1.0" or payload["case_id"] != case_id:
        raise ValueError(f"landmark file identity mismatch for {case_id}")
    frames_payload = payload["frames"]
    if not isinstance(frames_payload, list) or not 3 <= len(frames_payload) <= 2000:
        raise ValueError(f"landmark file for {case_id} must contain 3-2000 frames")

    frames: list[LandmarkFrame] = []
    timestamps: set[int] = set()
    for item in frames_payload:
        if not isinstance(item, dict) or set(item) != {
            "timestamp_ms",
            "handedness",
            "landmarks_xyz",
            "median_confidence",
            "validity",
        }:
            raise ValueError(f"landmark frame contract mismatch for {case_id}")
        timestamp = item["timestamp_ms"]
        if (
            isinstance(timestamp, bool)
            or not isinstance(timestamp, int)
            or not 0 <= timestamp <= 10000
            or timestamp in timestamps
        ):
            raise ValueError(f"landmark timestamps are invalid for {case_id}")
        timestamps.add(timestamp)
        if item["handedness"] != "right":
            raise ValueError(f"motor training v1 accepts right-hand tracking only: {case_id}")
        points = item["landmarks_xyz"]
        if not isinstance(points, list) or len(points) != 21:
            raise ValueError(f"landmark count is invalid for {case_id}")
        converted_points: list[tuple[float, float, float]] = []
        for point in points:
            if not isinstance(point, list) or len(point) != 3:
                raise ValueError(f"landmark coordinates are invalid for {case_id}")
            converted = tuple(float(value) for value in point)
            if not all(isfinite(value) for value in converted):
                raise ValueError(f"landmark coordinates are non-finite for {case_id}")
            converted_points.append(converted)
        confidence = float(item["median_confidence"])
        if not isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError(f"tracking confidence is invalid for {case_id}")
        try:
            validity = FrameValidity(item["validity"])
        except ValueError as error:
            raise ValueError(f"frame validity is invalid for {case_id}") from error
        frames.append(
            LandmarkFrame(
                timestamp_ms=timestamp,
                handedness="right",
                landmarks_xyz=tuple(converted_points),
                median_confidence=confidence,
                validity=validity,
            )
        )
    return sorted(frames, key=lambda frame: frame.timestamp_ms)


def load_motor_training_manifest(
    manifest_path: Path,
    *,
    data_root: Path,
    software_revision: str | None = None,
    working_tree_dirty: bool | None = None,
) -> tuple[list[MotorTrainingCase], MotorModelProvenance, dict[str, Any]]:
    """Load pseudonymous annotations and CV landmark tracks for training."""

    manifest = _validated_json(
        manifest_path,
        maximum_bytes=2_000_000,
        label="motor training manifest",
    )
    if not isinstance(manifest, dict):
        raise ValueError("motor training manifest must be a JSON object")
    schema = _validated_json(
        TRAINING_SCHEMA_PATH,
        maximum_bytes=1_000_000,
        label="motor training schema",
    )
    errors = sorted(
        Draft202012Validator(schema).iter_errors(manifest),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        details = "; ".join(
            f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
            f"{error.message}"
            for error in errors
        )
        raise ValueError(f"invalid motor training manifest: {details}")

    cases: list[MotorTrainingCase] = []
    case_ids: set[str] = set()
    agreement_threshold = FROZEN_THRESHOLDS[Modality.MOTOR].inter_rater_f1_min
    for case in manifest["cases"]:
        case_id = case["case_id"]
        if case_id in case_ids:
            raise ValueError(f"duplicate motor training case ID: {case_id}")
        case_ids.add(case_id)
        landmark_path = _contained_file(data_root, case["landmark_file"])
        frames = _landmark_frames(
            landmark_path,
            case_id=case_id,
            expected_sha256=case["landmark_sha256"],
        )
        rater_events = case["rater_events_ms"]
        reliability_scores = []
        for first, second in combinations(sorted(rater_events), 2):
            reliability_scores.append(
                score_event_agreement(
                    rater_events[first],
                    rater_events[second],
                    modality=Modality.MOTOR,
                    tolerance_ms=FROZEN_THRESHOLDS[Modality.MOTOR].tolerance_ms,
                )
            )
        for rater_id, events in sorted(rater_events.items()):
            reliability_scores.append(
                score_event_agreement(
                    case["consensus_events_ms"],
                    events,
                    modality=Modality.MOTOR,
                    tolerance_ms=FROZEN_THRESHOLDS[Modality.MOTOR].tolerance_ms,
                )
            )
        if any(
            score.f1 is None or score.f1 < agreement_threshold
            for score in reliability_scores
        ):
            raise ValueError(f"inter-rater agreement gate failed for {case_id}")
        cases.append(
            MotorTrainingCase(
                case_id=case_id,
                participant_id=case["participant_id"],
                split=case["split"],
                samples=tuple(derive_hand_signal(frames)),
                consensus_events_ms=tuple(sorted(case["consensus_events_ms"])),
                strata=dict(case["strata"]),
            )
        )

    dataset = manifest["dataset"]
    provenance = MotorModelProvenance(
        dataset_id=dataset["id"],
        dataset_doi=dataset["doi"],
        dataset_license=dataset["license"],
        dataset_kind=dataset["kind"],
        annotation_profile=manifest["profile_version"],
        human_annotated=bool(dataset["human_annotated"]),
        annotators_blinded_to_detector=bool(manifest["annotators_blinded_to_detector"]),
        participant_grouped_split=_participant_split_is_disjoint(cases),
        training_manifest_sha256=sha256(
            manifest_path.resolve(strict=True).read_bytes()
        ).hexdigest(),
        software_revision=software_revision,
        working_tree_dirty=working_tree_dirty,
    )
    return cases, provenance, manifest


def _quantile(values: np.ndarray, q: float) -> float:
    return float(np.quantile(values, q))


def build_temporal_features(samples: Sequence[HandSignalSample]) -> _TemporalRows:
    """Build local temporal features while retaining CV tracking quality.

    Invalid frames are never inference candidates. The local-validity and gap
    features prevent a learned detector from converting an occlusion into a
    confident event.
    """

    by_timestamp: dict[int, HandSignalSample] = {}
    for sample in samples:
        existing = by_timestamp.get(sample.timestamp_ms)
        if existing is None or (
            sample.valid
            and not existing.valid
        ) or (
            sample.valid == existing.valid
            and (sample.tracking_confidence or 0.0)
            > (existing.tracking_confidence or 0.0)
        ):
            by_timestamp[sample.timestamp_ms] = sample
    ordered = [by_timestamp[timestamp] for timestamp in sorted(by_timestamp)]
    valid_indices = [
        index
        for index, sample in enumerate(ordered)
        if (
            sample.valid
            and sample.normalized_thumb_index_distance is not None
            and isfinite(sample.normalized_thumb_index_distance)
        )
    ]
    if len(valid_indices) < 3:
        return _TemporalRows(
            timestamps_ms=np.empty(0, dtype=np.int64),
            features=np.empty((0, len(FEATURE_NAMES)), dtype=np.float64),
            amplitudes=np.empty(0, dtype=np.float64),
            local_valid_fraction=np.empty(0, dtype=np.float64),
        )

    distances = np.asarray(
        [ordered[index].normalized_thumb_index_distance for index in valid_indices],
        dtype=np.float64,
    )
    low = _quantile(distances, 0.10)
    high = _quantile(distances, 0.90)
    scale = high - low
    if scale <= 1e-9:
        scale = 1.0

    rows: list[list[float]] = []
    timestamps: list[int] = []
    amplitudes: list[float] = []
    valid_fractions: list[float] = []
    valid_position = {
        ordered_index: position
        for position, ordered_index in enumerate(valid_indices)
    }
    for ordered_index in valid_indices:
        position = valid_position[ordered_index]
        sample = ordered[ordered_index]
        current = float(sample.normalized_thumb_index_distance)
        previous_index = valid_indices[max(0, position - 1)]
        next_index = valid_indices[min(len(valid_indices) - 1, position + 1)]
        previous = ordered[previous_index]
        following = ordered[next_index]
        previous_value = float(previous.normalized_thumb_index_distance)
        next_value = float(following.normalized_thumb_index_distance)
        previous_gap = max(1, sample.timestamp_ms - previous.timestamp_ms)
        next_gap = max(1, following.timestamp_ms - sample.timestamp_ms)
        rising_velocity = (current - previous_value) / (previous_gap / 1000.0)
        falling_velocity = (current - next_value) / (next_gap / 1000.0)
        prominence = min(current - previous_value, current - next_value) / scale
        window = ordered[max(0, ordered_index - 2):ordered_index + 3]
        local_valid_fraction = sum(
            item.valid and item.normalized_thumb_index_distance is not None
            for item in window
        ) / len(window)
        confidence = (
            float(sample.tracking_confidence)
            if sample.tracking_confidence is not None
            else 0.5
        )
        angle = (
            float(sample.thumb_index_angle_rad) / pi
            if sample.thumb_index_angle_rad is not None
            and isfinite(sample.thumb_index_angle_rad)
            else 0.0
        )
        rows.append(
            [
                (current - low) / scale,
                angle,
                rising_velocity / scale,
                falling_velocity / scale,
                prominence,
                confidence,
                local_valid_fraction,
                min(1.0, max(previous_gap, next_gap) / 200.0),
            ]
        )
        timestamps.append(sample.timestamp_ms)
        amplitudes.append(current)
        valid_fractions.append(local_valid_fraction)

    return _TemporalRows(
        timestamps_ms=np.asarray(timestamps, dtype=np.int64),
        features=np.asarray(rows, dtype=np.float64),
        amplitudes=np.asarray(amplitudes, dtype=np.float64),
        local_valid_fraction=np.asarray(valid_fractions, dtype=np.float64),
    )


def _labels_for_rows(rows: _TemporalRows, events_ms: Sequence[int]) -> np.ndarray:
    labels = np.zeros(len(rows.timestamps_ms), dtype=np.float64)
    for event_ms in sorted(set(events_ms)):
        if event_ms < 0:
            raise ValueError("consensus event timestamps must be non-negative")
        if not len(rows.timestamps_ms):
            continue
        nearest = int(np.argmin(np.abs(rows.timestamps_ms - event_ms)))
        if abs(int(rows.timestamps_ms[nearest]) - event_ms) <= LABEL_TOLERANCE_MS:
            labels[nearest] = 1.0
    return labels


def _sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def _select_events(
    rows: _TemporalRows,
    probabilities: np.ndarray,
    *,
    threshold: float,
    minimum_separation_ms: int,
) -> tuple[list[int], list[float], list[float]]:
    candidates: list[tuple[int, float, float]] = []
    for index, probability in enumerate(probabilities):
        tracking_confidence = rows.features[index, FEATURE_NAMES.index("tracking_confidence")]
        if (
            probability < threshold
            or rows.local_valid_fraction[index] < 0.8
            or tracking_confidence < MINIMUM_TRACKING_CONFIDENCE
        ):
            continue
        previous_probability = probabilities[index - 1] if index > 0 else -1.0
        next_probability = probabilities[index + 1] if index + 1 < len(probabilities) else -1.0
        if probability >= previous_probability and probability > next_probability:
            candidates.append(
                (
                    int(rows.timestamps_ms[index]),
                    float(rows.amplitudes[index]),
                    float(probability),
                )
            )

    selected: list[tuple[int, float, float]] = []
    for candidate in candidates:
        if not selected or candidate[0] - selected[-1][0] >= minimum_separation_ms:
            selected.append(candidate)
        elif candidate[2] > selected[-1][2]:
            selected[-1] = candidate
    return (
        [item[0] for item in selected],
        [item[1] for item in selected],
        [item[2] for item in selected],
    )


def _pooled_agreement(
    cases: Sequence[MotorTrainingCase],
    predictions: Mapping[str, Sequence[int]],
) -> EventAgreement:
    reference_count = detected_count = matched_count = total_error = 0
    tolerance = FROZEN_THRESHOLDS[Modality.MOTOR].tolerance_ms
    for case in cases:
        score = score_event_agreement(
            case.consensus_events_ms,
            predictions[case.case_id],
            modality=Modality.MOTOR,
            tolerance_ms=tolerance,
        )
        reference_count += score.reference_count
        detected_count += score.detected_count
        matched_count += score.matched_count
        total_error += score.total_abs_timing_error_ms
    precision = matched_count / detected_count if detected_count else None
    recall = matched_count / reference_count if reference_count else None
    if precision is None or recall is None or precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return EventAgreement(
        reference_count=reference_count,
        detected_count=detected_count,
        matched_count=matched_count,
        precision=precision,
        recall=recall,
        f1=f1,
        timing_mae_ms=total_error / matched_count if matched_count else None,
        total_abs_timing_error_ms=total_error,
        tolerance_ms=tolerance,
    )


def _agreement_dict(score: EventAgreement) -> dict[str, Any]:
    values = asdict(score)
    values.pop("total_abs_timing_error_ms")
    return values


def _case_probabilities(
    cases: Sequence[MotorTrainingCase],
    *,
    mean: np.ndarray,
    scale: np.ndarray,
    weights: np.ndarray,
    bias: float,
) -> dict[str, tuple[_TemporalRows, np.ndarray]]:
    result: dict[str, tuple[_TemporalRows, np.ndarray]] = {}
    for case in cases:
        rows = build_temporal_features(case.samples)
        normalized = (rows.features - mean) / scale
        result[case.case_id] = (rows, _sigmoid(normalized @ weights + bias))
    return result


def _participant_split_is_disjoint(cases: Sequence[MotorTrainingCase]) -> bool:
    participants: dict[str, str] = {}
    for case in cases:
        existing = participants.setdefault(case.participant_id, case.split)
        if existing != case.split:
            return False
    return True


def _coverage_report(cases: Sequence[MotorTrainingCase]) -> dict[str, Any]:
    thresholds = FROZEN_THRESHOLDS[Modality.MOTOR]
    requirements = {
        "device": thresholds.minimum_device_strata,
        "condition": thresholds.minimum_condition_strata,
        "performance_band": thresholds.minimum_performance_band_strata,
    }
    details: dict[str, Any] = {}
    passed = True
    for field_name, minimum_distinct in requirements.items():
        counts: dict[str, int] = {}
        for case in cases:
            value = case.strata.get(field_name)
            if value:
                counts[value] = counts.get(value, 0) + 1
        field_passed = bool(
            len(counts) >= minimum_distinct
            and counts
            and min(counts.values()) >= thresholds.minimum_cases_per_required_stratum
        )
        passed = passed and field_passed
        details[field_name] = {
            "counts": dict(sorted(counts.items())),
            "minimum_distinct_values": minimum_distinct,
            "minimum_cases_per_value": thresholds.minimum_cases_per_required_stratum,
            "passed": field_passed,
        }
    return {"passed": passed, "fields": details}


def train_temporal_motor_model(
    cases: Sequence[MotorTrainingCase],
    *,
    provenance: MotorModelProvenance,
    model_version: str,
    epochs: int = 1000,
    learning_rate: float = 0.03,
    l2: float = 0.001,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Train a compact temporal classifier and evaluate untouched test cases."""

    if not model_version or len(model_version) > 80:
        raise ValueError("model_version must contain 1-80 characters")
    if epochs <= 0 or learning_rate <= 0 or l2 < 0:
        raise ValueError("invalid training hyperparameters")
    if not _participant_split_is_disjoint(cases):
        raise ValueError("participant leakage detected between train/validation/test splits")
    split_cases = {
        split: [case for case in cases if case.split == split]
        for split in ("train", "validation", "test")
    }
    if any(not split_cases[split] for split in split_cases):
        raise ValueError("training requires non-empty train, validation, and test splits")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("training case IDs must be unique")
    if any(not case.participant_id for case in cases):
        raise ValueError("every training case requires a participant ID")

    train_matrices: list[np.ndarray] = []
    train_labels: list[np.ndarray] = []
    for case in split_cases["train"]:
        rows = build_temporal_features(case.samples)
        labels = _labels_for_rows(rows, case.consensus_events_ms)
        if not len(rows.features) or not np.any(labels):
            raise ValueError(f"training case {case.case_id} has no usable annotated events")
        train_matrices.append(rows.features)
        train_labels.append(labels)
    x_train = np.vstack(train_matrices)
    y_train = np.concatenate(train_labels)
    mean = np.mean(x_train, axis=0)
    scale = np.std(x_train, axis=0)
    scale[scale < 1e-8] = 1.0
    normalized = (x_train - mean) / scale
    weights = np.zeros(normalized.shape[1], dtype=np.float64)
    bias = 0.0
    positive_count = float(np.sum(y_train))
    negative_count = float(len(y_train) - positive_count)
    positive_weight = min(25.0, max(1.0, negative_count / max(1.0, positive_count)))
    sample_weights = np.where(y_train == 1.0, positive_weight, 1.0)
    denominator = float(np.sum(sample_weights))
    for _ in range(epochs):
        probabilities = _sigmoid(normalized @ weights + bias)
        weighted_error = sample_weights * (probabilities - y_train)
        gradient = (normalized.T @ weighted_error) / denominator + l2 * weights
        bias_gradient = float(np.sum(weighted_error) / denominator)
        weights -= learning_rate * gradient
        bias -= learning_rate * bias_gradient

    all_probabilities = _case_probabilities(
        cases,
        mean=mean,
        scale=scale,
        weights=weights,
        bias=bias,
    )
    best_threshold = 0.5
    best_score = -1.0
    for threshold in np.linspace(0.10, 0.90, 33):
        predictions = {}
        for case in split_cases["validation"]:
            rows, probabilities = all_probabilities[case.case_id]
            predictions[case.case_id] = _select_events(
                rows,
                probabilities,
                threshold=float(threshold),
                minimum_separation_ms=MINIMUM_SEPARATION_MS,
            )[0]
        score = _pooled_agreement(split_cases["validation"], predictions)
        candidate = score.f1 or 0.0
        if candidate > best_score:
            best_score = candidate
            best_threshold = float(threshold)

    split_reports: dict[str, dict[str, Any]] = {}
    for split, selected_cases in split_cases.items():
        predictions = {}
        for case in selected_cases:
            rows, probabilities = all_probabilities[case.case_id]
            predictions[case.case_id] = _select_events(
                rows,
                probabilities,
                threshold=best_threshold,
                minimum_separation_ms=MINIMUM_SEPARATION_MS,
            )[0]
        split_reports[split] = {
            "case_count": len(selected_cases),
            **_agreement_dict(_pooled_agreement(selected_cases, predictions)),
        }

    thresholds = FROZEN_THRESHOLDS[Modality.MOTOR]
    test = split_reports["test"]
    coverage = _coverage_report(split_cases["test"])
    release_gate_passed = bool(
        provenance.dataset_kind == "human_recordings"
        and provenance.human_annotated
        and provenance.annotators_blinded_to_detector
        and provenance.participant_grouped_split
        and bool(provenance.software_revision)
        and provenance.working_tree_dirty is False
        and test["case_count"] >= thresholds.minimum_evaluable_cases
        and coverage["passed"]
        and test["precision"] is not None
        and test["precision"] >= thresholds.detector_precision_min
        and test["recall"] is not None
        and test["recall"] >= thresholds.detector_recall_min
        and test["f1"] is not None
        and test["f1"] >= thresholds.detector_f1_min
        and test["timing_mae_ms"] is not None
        and test["timing_mae_ms"] <= thresholds.detector_timing_mae_ms_max
    )
    report = {
        "participant_split_disjoint": True,
        **split_reports,
        "test_coverage": coverage,
        "selected_probability_threshold": best_threshold,
        "release_gate_passed": release_gate_passed,
        "scope_statement": (
            "A pass supports motor-event agreement with human annotations only; "
            "it does not establish Parkinson's diagnosis or clinical utility."
        ),
    }
    artifact = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "model_type": MODEL_TYPE,
        "model_version": model_version,
        "feature_names": list(FEATURE_NAMES),
        "parameters": {
            "feature_mean": mean.tolist(),
            "feature_scale": scale.tolist(),
            "weights": weights.tolist(),
            "bias": bias,
            "probability_threshold": best_threshold,
            "minimum_separation_ms": MINIMUM_SEPARATION_MS,
        },
        "provenance": asdict(provenance),
        "validation": report,
    }
    validate_motor_model_artifact(artifact, require_release_gate=False)
    return artifact, report


def _finite_number_list(value: Any, *, name: str) -> list[float]:
    if not isinstance(value, list) or len(value) != len(FEATURE_NAMES):
        raise ValueError(f"{name} must match the frozen feature contract")
    converted = [float(item) for item in value]
    if not all(isfinite(item) for item in converted):
        raise ValueError(f"{name} contains non-finite values")
    return converted


def validate_motor_model_artifact(
    artifact: Mapping[str, Any],
    *,
    require_release_gate: bool,
) -> None:
    required = {
        "schema_version",
        "model_type",
        "model_version",
        "feature_names",
        "parameters",
        "provenance",
        "validation",
    }
    if set(artifact) != required:
        raise ValueError("motor model artifact fields do not match the frozen contract")
    if artifact["schema_version"] != ARTIFACT_SCHEMA_VERSION:
        raise ValueError("unsupported motor model artifact schema")
    if artifact["model_type"] != MODEL_TYPE:
        raise ValueError("unsupported motor model type")
    if artifact["feature_names"] != list(FEATURE_NAMES):
        raise ValueError("motor model feature contract mismatch")
    if not isinstance(artifact["model_version"], str) or not artifact["model_version"]:
        raise ValueError("motor model version is required")

    parameters = artifact["parameters"]
    expected_parameters = {
        "feature_mean",
        "feature_scale",
        "weights",
        "bias",
        "probability_threshold",
        "minimum_separation_ms",
    }
    if not isinstance(parameters, Mapping) or set(parameters) != expected_parameters:
        raise ValueError("motor model parameters do not match the frozen contract")
    _finite_number_list(parameters["feature_mean"], name="feature_mean")
    feature_scale = _finite_number_list(parameters["feature_scale"], name="feature_scale")
    if any(value <= 0 for value in feature_scale):
        raise ValueError("feature_scale values must be positive")
    _finite_number_list(parameters["weights"], name="weights")
    if not isfinite(float(parameters["bias"])):
        raise ValueError("motor model bias must be finite")
    threshold = float(parameters["probability_threshold"])
    if not 0 < threshold < 1:
        raise ValueError("motor model probability threshold must be between zero and one")
    if int(parameters["minimum_separation_ms"]) < 50:
        raise ValueError("motor model minimum separation is unsafe")

    provenance = artifact["provenance"]
    if not isinstance(provenance, Mapping):
        raise ValueError("motor model provenance is required")
    validation = artifact["validation"]
    if not isinstance(validation, Mapping):
        raise ValueError("motor model validation report is required")
    if require_release_gate:
        if provenance.get("dataset_kind") != "human_recordings" or not provenance.get(
            "human_annotated"
        ):
            raise ValueError("release motor models require human-annotated recordings")
        if not provenance.get("annotators_blinded_to_detector"):
            raise ValueError("release motor models require blinded annotators")
        if not provenance.get("participant_grouped_split"):
            raise ValueError("release motor models require participant-grouped evaluation")
        if not provenance.get("software_revision"):
            raise ValueError("release motor models require a recorded software revision")
        if provenance.get("working_tree_dirty") is not False:
            raise ValueError("release motor models must be trained from a clean working tree")
        if not validation.get("release_gate_passed"):
            raise ValueError("motor model did not pass the frozen release gate")
        test = validation.get("test")
        coverage = validation.get("test_coverage")
        if not isinstance(test, Mapping) or not isinstance(coverage, Mapping):
            raise ValueError("motor model release validation is incomplete")
        thresholds = FROZEN_THRESHOLDS[Modality.MOTOR]
        timing_mae = test.get("timing_mae_ms")
        if (
            int(test.get("case_count", 0)) < thresholds.minimum_evaluable_cases
            or float(test.get("precision") or 0.0) < thresholds.detector_precision_min
            or float(test.get("recall") or 0.0) < thresholds.detector_recall_min
            or float(test.get("f1") or 0.0) < thresholds.detector_f1_min
            or timing_mae is None
            or float(timing_mae) > thresholds.detector_timing_mae_ms_max
            or coverage.get("passed") is not True
        ):
            raise ValueError("motor model release metrics do not pass the frozen gate")


class TemporalMotorEventModel:
    def __init__(
        self,
        *,
        artifact: Mapping[str, Any],
        artifact_sha256: str,
    ) -> None:
        parameters = artifact["parameters"]
        self.model_version = str(artifact["model_version"])
        self.artifact_sha256 = artifact_sha256
        self.mean = np.asarray(parameters["feature_mean"], dtype=np.float64)
        self.scale = np.asarray(parameters["feature_scale"], dtype=np.float64)
        self.weights = np.asarray(parameters["weights"], dtype=np.float64)
        self.bias = float(parameters["bias"])
        self.threshold = float(parameters["probability_threshold"])
        self.minimum_separation_ms = int(parameters["minimum_separation_ms"])
        self.provenance = dict(artifact["provenance"])
        self.release_gate_passed = bool(artifact["validation"]["release_gate_passed"])

    @classmethod
    def from_artifact(
        cls,
        artifact: Mapping[str, Any],
        *,
        require_release_gate: bool = True,
    ) -> "TemporalMotorEventModel":
        validate_motor_model_artifact(
            artifact,
            require_release_gate=require_release_gate,
        )
        canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return cls(artifact=artifact, artifact_sha256=sha256(canonical).hexdigest())

    def detect(self, samples: Sequence[HandSignalSample]) -> MotorEventDetection:
        rows = build_temporal_features(samples)
        if not len(rows.features):
            times: list[int] = []
            amplitudes: list[float] = []
            confidences: list[float] = []
        else:
            probabilities = _sigmoid(
                ((rows.features - self.mean) / self.scale) @ self.weights + self.bias
            )
            times, amplitudes, confidences = _select_events(
                rows,
                probabilities,
                threshold=self.threshold,
                minimum_separation_ms=self.minimum_separation_ms,
            )
        algorithm_version = (
            f"motor-ml:{self.model_version}:{self.artifact_sha256[:12]}"
        )
        return MotorEventDetection(
            timestamps_ms=tuple(times),
            amplitudes=tuple(amplitudes),
            confidences=tuple(confidences),
            detector_kind=MODEL_TYPE,
            algorithm_version=algorithm_version,
            metadata={
                "model_version": self.model_version,
                "artifact_sha256": self.artifact_sha256,
                "dataset_id": self.provenance.get("dataset_id"),
                "release_gate_passed": self.release_gate_passed,
                "clinical_validity": False,
            },
        )


def load_temporal_motor_model(
    path: Path,
    *,
    require_release_gate: bool = True,
) -> TemporalMotorEventModel:
    resolved = path.resolve(strict=True)
    if resolved.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ValueError("motor model artifact exceeds the safe size limit")
    raw = resolved.read_bytes()
    try:
        artifact = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("motor model artifact is not valid JSON") from error
    if not isinstance(artifact, dict):
        raise ValueError("motor model artifact must be a JSON object")
    validate_motor_model_artifact(
        artifact,
        require_release_gate=require_release_gate,
    )
    return TemporalMotorEventModel(
        artifact=artifact,
        artifact_sha256=sha256(raw).hexdigest(),
    )
