"""Assemble hash-bound motor training manifests from blinded rater exports."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
ANNOTATION_SCHEMA_PATH = ROOT / "validation" / "schemas" / "motor_annotation.v1.schema.json"
STUDY_PLAN_SCHEMA_PATH = ROOT / "validation" / "schemas" / "motor_study_plan.v1.schema.json"
TRAINING_SCHEMA_PATH = ROOT / "validation" / "schemas" / "motor_training_manifest.v1.schema.json"
MAXIMUM_PLAN_BYTES = 2_000_000
MAXIMUM_ANNOTATION_BYTES = 1_000_000
MAXIMUM_LANDMARK_BYTES = 25_000_000


def _read_json(path: Path, *, maximum_bytes: int, label: str) -> Any:
    resolved = path.resolve(strict=True)
    if resolved.stat().st_size > maximum_bytes:
        raise ValueError(f"{label} exceeds the safe size limit")
    try:
        return json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} is not valid JSON") from error


def _validate(payload: Any, schema_path: Path, *, label: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must be a JSON object")
    schema = _read_json(schema_path, maximum_bytes=1_000_000, label=f"{label} schema")
    errors = sorted(
        Draft202012Validator(schema).iter_errors(payload),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        details = "; ".join(
            f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
            f"{error.message}"
            for error in errors
        )
        raise ValueError(f"invalid {label}: {details}")
    return payload


def _contained_file(data_root: Path, relative_path: str, *, label: str) -> Path:
    root = data_root.resolve(strict=True)
    candidate = (root / relative_path).resolve(strict=True)
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise ValueError(f"{label} escapes or is missing from the configured data root")
    return candidate


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ordered_events(values: Any, *, label: str) -> list[int]:
    events = [int(value) for value in values]
    if events != sorted(events):
        raise ValueError(f"{label} must be in ascending timestamp order")
    return events


def _validate_landmark_identity(path: Path, *, case_id: str) -> None:
    payload = _read_json(
        path,
        maximum_bytes=MAXIMUM_LANDMARK_BYTES,
        label=f"landmark file for {case_id}",
    )
    if not isinstance(payload, Mapping) or payload.get("case_id") != case_id:
        raise ValueError(f"landmark case identity mismatch for {case_id}")


def _participant_splits_are_disjoint(cases: list[Mapping[str, Any]]) -> bool:
    participants: dict[str, str] = {}
    for case in cases:
        participant_id = str(case["participant_id"])
        split = str(case["split"])
        existing = participants.setdefault(participant_id, split)
        if existing != split:
            return False
    return True


def assemble_motor_training_manifest(
    plan_path: Path,
    *,
    data_root: Path,
) -> dict[str, Any]:
    """Combine independent annotations and verified source files for training."""

    plan = _validate(
        _read_json(
            plan_path,
            maximum_bytes=MAXIMUM_PLAN_BYTES,
            label="motor study plan",
        ),
        STUDY_PLAN_SCHEMA_PATH,
        label="motor study plan",
    )
    cases = list(plan["cases"])
    if len({str(case["case_id"]) for case in cases}) != len(cases):
        raise ValueError("motor study plan contains duplicate case IDs")
    if not _participant_splits_are_disjoint(cases):
        raise ValueError("participant leakage detected between study splits")

    assembled_cases: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case["case_id"])
        landmark_relative = str(case["landmark_file"])
        landmark_path = _contained_file(
            data_root,
            landmark_relative,
            label=f"landmark file for {case_id}",
        )
        _validate_landmark_identity(landmark_path, case_id=case_id)
        source_video_path = _contained_file(
            data_root,
            str(case["source_video_file"]),
            label=f"source video for {case_id}",
        )

        rater_events: dict[str, list[int]] = {}
        for relative_path in case["rater_annotation_files"]:
            annotation_path = _contained_file(
                data_root,
                str(relative_path),
                label=f"annotation for {case_id}",
            )
            annotation = _validate(
                _read_json(
                    annotation_path,
                    maximum_bytes=MAXIMUM_ANNOTATION_BYTES,
                    label=f"annotation for {case_id}",
                ),
                ANNOTATION_SCHEMA_PATH,
                label=f"motor annotation for {case_id}",
            )
            if annotation["case_id"] != case_id:
                raise ValueError(f"annotation case identity mismatch for {case_id}")
            rater_id = str(annotation["rater_id"])
            if rater_id in rater_events:
                raise ValueError(f"duplicate rater ID for {case_id}: {rater_id}")
            rater_events[rater_id] = _ordered_events(
                annotation["event_times_ms"],
                label=f"events from {rater_id} for {case_id}",
            )

        assembled_cases.append(
            {
                "case_id": case_id,
                "participant_id": case["participant_id"],
                "split": case["split"],
                "task_code": case["task_code"],
                "hand": case["hand"],
                "landmark_file": Path(landmark_relative).as_posix(),
                "landmark_sha256": _sha256_file(landmark_path),
                "source_video_sha256": _sha256_file(source_video_path),
                "strata": dict(case["strata"]),
                "rater_events_ms": dict(sorted(rater_events.items())),
                "consensus_events_ms": _ordered_events(
                    case["consensus_events_ms"],
                    label=f"consensus events for {case_id}",
                ),
            }
        )

    manifest = {
        "schema_version": "1.0",
        "profile_version": "handvoice-motor-training-v1",
        "claim_boundary": plan["claim_boundary"],
        "annotators_blinded_to_detector": plan["annotators_blinded_to_detector"],
        "consensus_adjudicated_without_detector": plan[
            "consensus_adjudicated_without_detector"
        ],
        "dataset": dict(plan["dataset"]),
        "cases": assembled_cases,
    }
    _validate(manifest, TRAINING_SCHEMA_PATH, label="motor training manifest")
    return manifest
