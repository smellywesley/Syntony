from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml

from services.api.app.core.config import get_settings


@lru_cache

def load_protocol(path: str | None = None) -> dict[str, Any]:
    protocol_path = Path(path) if path else get_settings().protocol_path
    with protocol_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    codes = {task["code"] for task in data["task_definitions"]}
    for name, sequence in data["sequences"].items():
        if set(sequence) != codes:
            raise ValueError(f"sequence {name} does not contain each task code exactly once")
    return data


def choose_sequence(participant_id: str, session_number: int, protocol: dict[str, Any]) -> str:
    sequence_ids = sorted(protocol["sequences"])
    digest_value = int.from_bytes(sha256(participant_id.encode("utf-8")).digest()[:8], "big")
    return sequence_ids[(digest_value + session_number - 1) % len(sequence_ids)]


def expand_task_instances(protocol: dict[str, Any], sequence_id: str) -> list[dict[str, Any]]:
    definitions = {task["code"]: task for task in protocol["task_definitions"]}
    repetitions = int(protocol["repetitions"])
    expanded: list[dict[str, Any]] = []
    order_index = 0
    for code in protocol["sequences"][sequence_id]:
        definition = definitions[code]
        for repetition in range(1, repetitions + 1):
            expanded.append({**definition, "repetition": repetition, "order_index": order_index})
            order_index += 1
    return expanded
