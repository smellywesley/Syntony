import json
from pathlib import Path

from pipelines.quality.decision import AudioQualityMetrics, assess_capture_quality
from services.api.app.services.protocol import load_protocol


FIXTURE = Path(__file__).parents[1] / "fixtures" / "qc_golden_v1.json"


def _base_inputs() -> dict:
    return {
        "protocol": load_protocol("configs/protocol.v1.yaml"),
        "requires_hand": True,
        "requires_speech": True,
        "median_fps": 30.0,
        "valid_frame_fraction": 0.95,
        "out_of_guide_frame_fraction": 0.0,
        "audio": AudioQualityMetrics(20.0, 0.0, True),
        "av_start_offset_ms": 0.0,
        "motor_event_count": 10,
        "ddk_event_count": 10,
        "audio_decode_failed": False,
        "capture_interrupted": False,
        "wrong_hand_frame_fraction": 0.0,
    }


def test_versioned_thirty_case_qc_golden_set_matches_exactly():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fixture["fixture_version"] == "qc-golden-v1"
    assert fixture["protocol_version"] == "1.1.0"
    assert len(fixture["cases"]) == 30
    assert len({case["id"] for case in fixture["cases"]}) == 30

    for case in fixture["cases"]:
        inputs = _base_inputs()
        overrides = dict(case["overrides"])
        if isinstance(overrides.get("audio"), dict):
            overrides["audio"] = AudioQualityMetrics(**overrides["audio"])
        inputs.update(overrides)

        result = assess_capture_quality(**inputs)

        assert result.decision.value == case["decision"], case["id"]
        assert [reason.value for reason in result.reason_codes] == case["reasons"], case["id"]


def test_wrong_hand_is_a_structured_retry_decision():
    inputs = _base_inputs()
    inputs["wrong_hand_frame_fraction"] = 0.20
    result = assess_capture_quality(**inputs)
    assert result.decision.value == "retry"
    assert [reason.value for reason in result.reason_codes] == ["wrong_hand"]
