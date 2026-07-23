from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from services.api.app.services.protocol import choose_sequence, expand_task_instances, load_protocol


def test_protocol_creates_only_three_first_pass_tasks():
    protocol = load_protocol("configs/protocol.v1.yaml")
    items = expand_task_instances(protocol, "A")
    assert len(items) == 3
    assert [item["code"] for item in items] == ["T01", "T02", "T03"]
    assert all(item["repetition"] == 1 for item in items)


def test_sequence_is_deterministic_and_rotates_by_session():
    protocol = load_protocol("configs/protocol.v1.yaml")
    first = choose_sequence("participant-1", 1, protocol)
    assert first == choose_sequence("participant-1", 1, protocol)
    second = choose_sequence("participant-1", 2, protocol)
    assert first != second


def test_duplicate_task_code_in_sequence_is_rejected(tmp_path: Path):
    protocol = deepcopy(load_protocol("configs/protocol.v1.yaml"))
    protocol["sequences"]["A"] = ["T01", "T02", "T02"]
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(protocol), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly once"):
        load_protocol(str(path))


def test_quality_defaults_are_required_and_fully_schematized(tmp_path: Path):
    protocol = deepcopy(load_protocol("configs/protocol.v1.yaml"))
    del protocol["quality_defaults"]["audio"]["accept_snr_db"]
    path = tmp_path / "missing-quality-threshold.yaml"
    path.write_text(yaml.safe_dump(protocol), encoding="utf-8")
    load_protocol.cache_clear()
    with pytest.raises(ValueError, match="required property"):
        load_protocol(str(path))


@pytest.mark.parametrize(
    ("section", "accept_key", "reject_key"),
    [
        ("video", "accept_valid_frame_fraction", "reject_valid_frame_fraction"),
        ("video", "accept_median_fps", "reject_median_fps"),
        ("audio", "accept_snr_db", "reject_snr_db"),
    ],
)
def test_higher_is_better_quality_thresholds_must_be_ordered(
    tmp_path: Path,
    section: str,
    accept_key: str,
    reject_key: str,
):
    protocol = deepcopy(load_protocol("configs/protocol.v1.yaml"))
    protocol["quality_defaults"][section][accept_key] = protocol["quality_defaults"][section][reject_key]
    path = tmp_path / f"reversed-{section}-{accept_key}.yaml"
    path.write_text(yaml.safe_dump(protocol), encoding="utf-8")
    load_protocol.cache_clear()
    with pytest.raises(ValueError, match="must exceed"):
        load_protocol(str(path))


@pytest.mark.parametrize(
    ("section", "accept_key", "reject_key"),
    [
        ("video", "accept_wrong_hand_fraction", "reject_wrong_hand_fraction"),
        ("audio", "accept_clipping_fraction", "reject_clipping_fraction"),
        ("synchronization", "accept_start_offset_ms", "reject_start_offset_ms"),
    ],
)
def test_lower_is_better_quality_thresholds_must_be_ordered(
    tmp_path: Path,
    section: str,
    accept_key: str,
    reject_key: str,
):
    protocol = deepcopy(load_protocol("configs/protocol.v1.yaml"))
    protocol["quality_defaults"][section][reject_key] = protocol["quality_defaults"][section][accept_key]
    path = tmp_path / f"reversed-{section}-{reject_key}.yaml"
    path.write_text(yaml.safe_dump(protocol), encoding="utf-8")
    load_protocol.cache_clear()
    with pytest.raises(ValueError, match="must exceed"):
        load_protocol(str(path))


def test_equal_priority_instruction_is_required_and_true(tmp_path: Path):
    protocol = deepcopy(load_protocol("configs/protocol.v1.yaml"))
    protocol["equal_priority_instruction_required"] = False
    path = tmp_path / "equal-priority-disabled.yaml"
    path.write_text(yaml.safe_dump(protocol), encoding="utf-8")
    load_protocol.cache_clear()
    with pytest.raises(ValueError, match="True was expected"):
        load_protocol(str(path))


def test_task_modalities_are_frozen_by_code(tmp_path: Path):
    protocol = deepcopy(load_protocol("configs/protocol.v1.yaml"))
    protocol["task_definitions"][0]["hand"] = "left"
    path = tmp_path / "wrong-task-modality.yaml"
    path.write_text(yaml.safe_dump(protocol), encoding="utf-8")
    load_protocol.cache_clear()
    with pytest.raises(ValueError, match="invalid modality definition"):
        load_protocol(str(path))
