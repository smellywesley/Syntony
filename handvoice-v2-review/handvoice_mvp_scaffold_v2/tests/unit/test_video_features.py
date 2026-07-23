from types import SimpleNamespace

from pipelines.video.contracts import FrameValidity
from pipelines.video.extractor import derive_hand_signal


def test_malformed_landmark_count_becomes_invalid_sample():
    frame = SimpleNamespace(
        timestamp_ms=100,
        landmarks_xyz=((0.0, 0.0, 0.0),) * 10,
        median_confidence=0.95,
        validity=FrameValidity.VALID,
    )
    result = derive_hand_signal([frame])
    assert result[0].valid is False
    assert result[0].quality_reason == "malformed_landmark_count"


def test_zero_palm_scale_becomes_invalid_sample():
    frame = SimpleNamespace(
        timestamp_ms=100,
        landmarks_xyz=((0.0, 0.0, 0.0),) * 21,
        median_confidence=0.95,
        validity=FrameValidity.VALID,
    )
    result = derive_hand_signal([frame])
    assert result[0].valid is False
    assert result[0].quality_reason == "invalid_palm_scale"
