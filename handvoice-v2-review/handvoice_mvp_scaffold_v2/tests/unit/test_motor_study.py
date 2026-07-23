from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from pipelines.video.motor_study import assemble_motor_training_manifest


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _annotation(case_id: str, rater_id: str, events: list[int]) -> dict:
    return {
        "schema_version": "1.0",
        "profile_version": "handvoice-motor-annotation-v1",
        "case_id": case_id,
        "rater_id": rater_id,
        "annotator_blinded_to_detector": True,
        "active_window_ms": 10000,
        "event_times_ms": events,
    }


def _plan(data_root: Path) -> tuple[Path, list[dict]]:
    cases: list[dict] = []
    for index, split in enumerate(("train", "validation", "test"), start=1):
        case_id = f"motor-{index:03d}"
        landmark_relative = f"landmarks/{case_id}.json"
        video_relative = f"videos/{case_id}.mp4"
        annotation_files = [
            f"annotations/{case_id}.rater-a.events.json",
            f"annotations/{case_id}.rater-b.events.json",
        ]
        _write_json(
            data_root / landmark_relative,
            {"schema_version": "1.0", "case_id": case_id, "frames": []},
        )
        video_path = data_root / video_relative
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(f"approved-video-{index}".encode())
        _write_json(
            data_root / annotation_files[0],
            _annotation(case_id, "rater-a", [400, 800, 1200]),
        )
        _write_json(
            data_root / annotation_files[1],
            _annotation(case_id, "rater-b", [410, 790, 1210]),
        )
        cases.append(
            {
                "case_id": case_id,
                "participant_id": f"participant-{index:03d}",
                "split": split,
                "task_code": "T01",
                "hand": "right",
                "source_video_file": video_relative,
                "landmark_file": landmark_relative,
                "rater_annotation_files": annotation_files,
                "consensus_events_ms": [405, 795, 1205],
                "strata": {
                    "device": f"device-{index}",
                    "condition": "clear",
                    "performance_band": "typical",
                },
            }
        )
    plan = {
        "schema_version": "1.0",
        "profile_version": "handvoice-motor-study-plan-v1",
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
    plan_path = data_root / "study-plan.json"
    _write_json(plan_path, plan)
    return plan_path, cases


def test_study_assembler_binds_video_landmark_and_blinded_annotations(tmp_path: Path):
    plan_path, source_cases = _plan(tmp_path)

    manifest = assemble_motor_training_manifest(plan_path, data_root=tmp_path)

    assert manifest["profile_version"] == "handvoice-motor-training-v1"
    assert len(manifest["cases"]) == 3
    first = manifest["cases"][0]
    assert first["rater_events_ms"] == {
        "rater-a": [400, 800, 1200],
        "rater-b": [410, 790, 1210],
    }
    assert first["landmark_sha256"] == sha256(
        (tmp_path / source_cases[0]["landmark_file"]).read_bytes()
    ).hexdigest()
    assert first["source_video_sha256"] == sha256(
        (tmp_path / source_cases[0]["source_video_file"]).read_bytes()
    ).hexdigest()
    assert "source_video_file" not in first
    assert "rater_annotation_files" not in first


def test_study_assembler_rejects_annotation_for_another_case(tmp_path: Path):
    plan_path, cases = _plan(tmp_path)
    annotation_path = tmp_path / cases[0]["rater_annotation_files"][0]
    payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    payload["case_id"] = "different-case"
    _write_json(annotation_path, payload)

    with pytest.raises(ValueError, match="case identity mismatch"):
        assemble_motor_training_manifest(plan_path, data_root=tmp_path)


def test_study_assembler_rejects_participant_split_leakage(tmp_path: Path):
    plan_path, _ = _plan(tmp_path)
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    payload["cases"][1]["participant_id"] = payload["cases"][0]["participant_id"]
    _write_json(plan_path, payload)

    with pytest.raises(ValueError, match="participant leakage"):
        assemble_motor_training_manifest(plan_path, data_root=tmp_path)


def test_study_assembler_rejects_paths_outside_data_root(tmp_path: Path):
    plan_path, _ = _plan(tmp_path)
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    payload["cases"][0]["landmark_file"] = "../outside.json"
    _write_json(plan_path, payload)

    with pytest.raises(ValueError, match="invalid motor study plan"):
        assemble_motor_training_manifest(plan_path, data_root=tmp_path)
