from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from math import exp
from pathlib import Path

import pytest

from pipelines.video.contracts import FrameValidity, LandmarkFrame
from pipelines.video.extractor import HandSignalSample, derive_hand_signal
from pipelines.video.motor_model import (
    MotorEventDetection,
    MotorModelProvenance,
    MotorTrainingCase,
    TemporalMotorEventModel,
    load_motor_training_manifest,
    train_temporal_motor_model,
    validate_motor_model_artifact,
)
from pipelines.measurement.core import analyze_measurement


def _case(
    case_id: str,
    participant_id: str,
    split: str,
    *,
    phase_ms: int,
    invalid_event_index: int | None = None,
) -> MotorTrainingCase:
    event_times = [phase_ms + index * 400 for index in range(1, 10)]
    samples: list[HandSignalSample] = []
    for timestamp in range(0, 4200, 40):
        distance = 0.15
        for event_time in event_times:
            distance += 0.9 * exp(-((timestamp - event_time) / 65.0) ** 2)
        nearest_event = min(
            range(len(event_times)),
            key=lambda index: abs(event_times[index] - timestamp),
        )
        invalid = (
            invalid_event_index is not None
            and nearest_event == invalid_event_index
            and abs(timestamp - event_times[nearest_event]) <= 40
        )
        samples.append(
            HandSignalSample(
                timestamp_ms=timestamp,
                thumb_index_angle_rad=0.3 + distance,
                normalized_thumb_index_distance=None if invalid else distance,
                valid=not invalid,
                quality_reason="missing_hand" if invalid else None,
                palm_scale=0.25 if not invalid else None,
                tracking_confidence=0.0 if invalid else 0.96,
            )
        )
    return MotorTrainingCase(
        case_id=case_id,
        participant_id=participant_id,
        split=split,
        samples=tuple(samples),
        consensus_events_ms=tuple(event_times),
    )


def _provenance() -> MotorModelProvenance:
    return MotorModelProvenance(
        dataset_id="HUBU-FIS-pilot",
        dataset_doi="10.5281/zenodo.17738775",
        dataset_license="CC-BY-4.0",
        dataset_kind="human_recordings",
        annotation_profile="handvoice-agreement-v1",
        human_annotated=True,
        annotators_blinded_to_detector=True,
        participant_grouped_split=True,
    )


def test_temporal_model_learns_events_and_preserves_tracking_gaps():
    cases = [
        _case("train-a", "participant-a", "train", phase_ms=0),
        _case("train-b", "participant-b", "train", phase_ms=20),
        _case("validation-a", "participant-c", "validation", phase_ms=10),
        _case("test-a", "participant-d", "test", phase_ms=30, invalid_event_index=4),
    ]

    artifact, report = train_temporal_motor_model(
        cases,
        provenance=_provenance(),
        model_version="motor-event-test",
        epochs=800,
        learning_rate=0.04,
    )
    model = TemporalMotorEventModel.from_artifact(artifact, require_release_gate=False)
    prediction = model.detect(list(cases[-1].samples))

    assert report["test"]["f1"] >= 0.85
    assert report["participant_split_disjoint"] is True
    assert all(
        abs(timestamp - cases[-1].consensus_events_ms[4]) > 80
        for timestamp in prediction.timestamps_ms
    )
    assert len(prediction.timestamps_ms) == len(prediction.confidences)
    assert prediction.detector_kind == "temporal_logistic"


def test_low_confidence_cv_frame_is_not_a_valid_motor_sample():
    points = tuple((0.0, 0.0, 0.0) for _ in range(21))
    samples = derive_hand_signal(
        [
            LandmarkFrame(
                timestamp_ms=400,
                handedness="right",
                landmarks_xyz=points,
                median_confidence=0.49,
                validity=FrameValidity.VALID,
            )
        ]
    )

    assert samples[0].valid is False
    assert samples[0].quality_reason == "low_tracking_confidence"
    assert samples[0].tracking_confidence == 0.49


def test_release_artifact_requires_human_annotations_and_grouped_participants():
    cases = [
        _case("train-a", "participant-a", "train", phase_ms=0),
        _case("validation-a", "participant-b", "validation", phase_ms=10),
        _case("test-a", "participant-c", "test", phase_ms=20),
    ]
    artifact, _ = train_temporal_motor_model(
        cases,
        provenance=_provenance(),
        model_version="motor-event-test",
        epochs=300,
        learning_rate=0.04,
    )

    invalid = deepcopy(artifact)
    invalid["provenance"]["human_annotated"] = False
    invalid["validation"]["release_gate_passed"] = True
    with pytest.raises(ValueError, match="human-annotated"):
        validate_motor_model_artifact(invalid, require_release_gate=True)

    invalid = deepcopy(artifact)
    invalid["provenance"]["participant_grouped_split"] = False
    invalid["validation"]["release_gate_passed"] = True
    with pytest.raises(ValueError, match="participant-grouped"):
        validate_motor_model_artifact(invalid, require_release_gate=True)

    invalid = deepcopy(artifact)
    invalid["provenance"]["software_revision"] = None
    invalid["provenance"]["working_tree_dirty"] = False
    invalid["validation"]["release_gate_passed"] = True
    with pytest.raises(ValueError, match="software revision"):
        validate_motor_model_artifact(invalid, require_release_gate=True)

    invalid = deepcopy(artifact)
    invalid["provenance"]["software_revision"] = "abc123"
    invalid["provenance"]["working_tree_dirty"] = True
    invalid["validation"]["release_gate_passed"] = True
    with pytest.raises(ValueError, match="clean working tree"):
        validate_motor_model_artifact(invalid, require_release_gate=True)


def test_training_rejects_participant_leakage_between_splits():
    cases = [
        _case("train-a", "participant-a", "train", phase_ms=0),
        _case("validation-a", "participant-a", "validation", phase_ms=10),
        _case("test-a", "participant-c", "test", phase_ms=20),
    ]

    with pytest.raises(ValueError, match="participant leakage"):
        train_temporal_motor_model(
            cases,
            provenance=_provenance(),
            model_version="motor-event-test",
        )


def test_measurement_pipeline_preserves_model_confidence_and_provenance():
    class StubModel:
        def detect(self, samples):
            assert samples
            return MotorEventDetection(
                timestamps_ms=(400, 800),
                amplitudes=(0.8, 0.7),
                confidences=(0.91, 0.87),
                detector_kind="temporal_logistic",
                algorithm_version="motor-ml:test:1234",
                metadata={"artifact_sha256": "1234", "clinical_validity": False},
            )

    samples = list(_case("case", "participant", "test", phase_ms=0).samples)
    result = analyze_measurement(
        active_duration_ms=4200,
        hand_samples=samples,
        voiced_intervals=[],
        ddk_event_ms=[],
        coupling_window_ms=80,
        motor_event_model=StubModel(),
    )

    assert [event.confidence for event in result.motor_events] == [0.91, 0.87]
    assert result.motor_events[0].metadata["detector_kind"] == "temporal_logistic"
    assert result.motor_detection is not None
    assert result.motor_detection.algorithm_version == "motor-ml:test:1234"


def _landmark_payload(case_id: str) -> dict:
    frames = []
    for timestamp in range(0, 2000, 40):
        distance = 0.2 + 0.8 * sum(
            exp(-((timestamp - event_time) / 65.0) ** 2)
            for event_time in (400, 800, 1200)
        )
        points = [[0.0, 0.0, 0.0] for _ in range(21)]
        points[4] = [-distance / 2, 0.2, 0.0]
        points[8] = [distance / 2, 0.2, 0.0]
        points[5] = [0.3, 0.0, 0.0]
        points[9] = [0.0, 0.3, 0.0]
        points[17] = [-0.3, 0.0, 0.0]
        frames.append(
            {
                "timestamp_ms": timestamp,
                "handedness": "right",
                "landmarks_xyz": points,
                "median_confidence": 0.95,
                "validity": "valid",
            }
        )
    return {"schema_version": "1.0", "case_id": case_id, "frames": frames}


def test_training_manifest_loads_verified_cv_tracks(tmp_path: Path):
    cases = []
    for index, split in enumerate(("train", "validation", "test"), start=1):
        case_id = f"motor-{index:03d}"
        landmark_path = tmp_path / f"{case_id}.json"
        raw = json.dumps(_landmark_payload(case_id)).encode()
        landmark_path.write_bytes(raw)
        cases.append(
            {
                "case_id": case_id,
                "participant_id": f"participant-{index:03d}",
                "split": split,
                "task_code": "T01",
                "hand": "right",
                "landmark_file": landmark_path.name,
                "landmark_sha256": sha256(raw).hexdigest(),
                "source_video_sha256": str(index) * 64,
                "strata": {
                    "device": f"device-{index}",
                    "condition": "clear",
                    "performance_band": "typical",
                },
                "rater_events_ms": {
                    "rater-a": [400, 800, 1200],
                    "rater-b": [410, 790, 1210],
                },
                "consensus_events_ms": [405, 795, 1205],
            }
        )
    manifest = {
        "schema_version": "1.0",
        "profile_version": "handvoice-motor-training-v1",
        "claim_boundary": "motor_event_measurement_only",
        "annotators_blinded_to_detector": True,
        "consensus_adjudicated_without_detector": True,
        "dataset": {
            "id": "HUBU-FIS-pilot",
            "doi": "10.5281/zenodo.17738775",
            "license": "CC-BY-4.0",
            "kind": "human_recordings",
            "human_annotated": True,
        },
        "cases": cases,
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    loaded, provenance, _ = load_motor_training_manifest(
        manifest_path,
        data_root=tmp_path,
    )

    assert len(loaded) == 3
    assert all(case.samples for case in loaded)
    assert provenance.dataset_id == "HUBU-FIS-pilot"
    assert provenance.participant_grouped_split is True
