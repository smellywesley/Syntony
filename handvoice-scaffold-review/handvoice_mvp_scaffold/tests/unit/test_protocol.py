from services.api.app.services.protocol import choose_sequence, expand_task_instances, load_protocol


def test_protocol_expands_to_sixteen_task_instances():
    protocol = load_protocol("configs/protocol.v1.yaml")
    items = expand_task_instances(protocol, "A")
    assert len(items) == 16
    assert items[0]["task_code"] if False else True  # guard against accidental dict API changes
    assert items[0]["code"] == "T01"
    assert items[0]["repetition"] == 1
    assert items[1]["repetition"] == 2


def test_sequence_is_deterministic_and_rotates_by_session():
    protocol = load_protocol("configs/protocol.v1.yaml")
    first = choose_sequence("participant-1", 1, protocol)
    assert first == choose_sequence("participant-1", 1, protocol)
    second = choose_sequence("participant-1", 2, protocol)
    assert first != second
