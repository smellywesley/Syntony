from __future__ import annotations

from collections import Counter
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import yaml

from services.api.app.core.config import get_settings


def _schema_path() -> Path:
    repository_root = Path(__file__).resolve().parents[4]
    return repository_root / "packages/protocol_schema/handvoice_protocol.schema.json"


def _validate_semantics(data: dict[str, Any]) -> None:
    definitions = data["task_definitions"]
    codes = [task["code"] for task in definitions]
    names = [task["name"] for task in definitions]
    if len(codes) != len(set(codes)):
        raise ValueError("task definition codes must be unique")
    if len(names) != len(set(names)):
        raise ValueError("task definition names must be unique")
    expected_tasks = {
        "T01": {"condition": "single", "hand": "right", "speech_task": None},
        "T02": {"condition": "single", "hand": None, "speech_task": "ddk_pataka"},
        "T03": {"condition": "dual", "hand": "right", "speech_task": "ddk_pataka"},
    }
    if set(codes) != set(expected_tasks):
        raise ValueError("protocol must define exactly T01, T02 and T03")
    for task in definitions:
        expected = expected_tasks[task["code"]]
        if any(task[key] != value for key, value in expected.items()):
            raise ValueError(f"task {task['code']} has an invalid modality definition")

    expected = Counter(codes)
    for name, sequence in data["sequences"].items():
        observed = Counter(sequence)
        if len(sequence) != len(codes) or observed != expected:
            raise ValueError(f"sequence {name} must contain every task code exactly once")
        if sequence[-1] != "T03":
            raise ValueError(f"sequence {name} must place the dual task after both baselines")

    if data["max_repetitions"] < data["initial_repetitions"]:
        raise ValueError("max_repetitions cannot be below initial_repetitions")

    quality = data["quality_defaults"]
    ordered_thresholds = [
        (
            quality["video"]["accept_valid_frame_fraction"],
            quality["video"]["reject_valid_frame_fraction"],
            "video valid-frame accept threshold must exceed reject threshold",
        ),
        (
            quality["video"]["accept_median_fps"],
            quality["video"]["reject_median_fps"],
            "video frame-rate accept threshold must exceed reject threshold",
        ),
        (
            quality["video"]["reject_wrong_hand_fraction"],
            quality["video"]["accept_wrong_hand_fraction"],
            "wrong-hand reject threshold must exceed accept threshold",
        ),
        (
            quality["audio"]["accept_snr_db"],
            quality["audio"]["reject_snr_db"],
            "audio SNR accept threshold must exceed reject threshold",
        ),
        (
            quality["audio"]["reject_clipping_fraction"],
            quality["audio"]["accept_clipping_fraction"],
            "audio clipping reject threshold must exceed accept threshold",
        ),
        (
            quality["synchronization"]["reject_start_offset_ms"],
            quality["synchronization"]["accept_start_offset_ms"],
            "A/V offset reject threshold must exceed accept threshold",
        ),
    ]
    for higher, lower, message in ordered_thresholds:
        if higher <= lower:
            raise ValueError(message)


@lru_cache
def load_protocol(path: str | None = None) -> dict[str, Any]:
    protocol_path = Path(path) if path else get_settings().protocol_path
    with protocol_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    with _schema_path().open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda error: list(error.path))
    if errors:
        summary = "; ".join(error.message for error in errors[:5])
        raise ValueError(f"protocol schema validation failed: {summary}")
    _validate_semantics(data)
    return data


def choose_sequence(participant_id: str, session_number: int, protocol: dict[str, Any]) -> str:
    sequence_ids = sorted(protocol["sequences"])
    digest_value = int.from_bytes(sha256(participant_id.encode("utf-8")).digest()[:8], "big")
    return sequence_ids[(digest_value + session_number - 1) % len(sequence_ids)]


def expand_task_instances(protocol: dict[str, Any], sequence_id: str) -> list[dict[str, Any]]:
    definitions = {task["code"]: task for task in protocol["task_definitions"]}
    repetitions = int(protocol["initial_repetitions"])
    expanded: list[dict[str, Any]] = []
    order_index = 0
    for code in protocol["sequences"][sequence_id]:
        definition = definitions[code]
        for repetition in range(1, repetitions + 1):
            expanded.append({**definition, "repetition": repetition, "order_index": order_index})
            order_index += 1
    return expanded
