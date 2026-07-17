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
