import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from pipelines.measurement.core import detect_tap_events
from pipelines.video.extractor import HandSignalSample
from services.api.app.schemas.api import CaptureManifest, MeasurementSubmission
from services.api.app.services.measurement import _validate_task_payload
from services.api.app.services.media import probe_media


def _manifest(**overrides: int | str) -> dict[str, int | str]:
    values: dict[str, int | str] = {
        "protocol_version": "1.1.0",
        "active_start_ms": 2000,
        "active_end_ms": 12000,
        "camera_facing": "front",
        "capture_app_version": "test-0.1",
    }
    values.update(overrides)
    return values


def _submission(*, hand: bool = False, speech: bool = False) -> MeasurementSubmission:
    landmarks = [(0.0, 0.0, 0.0)] * 21
    return MeasurementSubmission(
        storage_key="capture.mp4",
        sha256="0" * 64,
        manifest=_manifest(),
        landmark_frames=(
            [
                {
                    "timestamp_ms": 0,
                    "handedness": "right",
                    "landmarks_xyz": landmarks,
                    "median_confidence": 0.9,
                    "validity": "valid",
                }
            ]
            if hand
            else []
        ),
        ddk_event_ms=[100, 300, 500, 700, 900] if speech else [],
    )


def test_capture_manifest_rejects_shifted_ten_second_window():
    with pytest.raises(ValidationError, match="frozen 2000-12000"):
        CaptureManifest.model_validate(_manifest(active_start_ms=3000, active_end_ms=13000))


@pytest.mark.parametrize(
    ("task_code", "hand", "speech", "error"),
    [
        ("T01", True, True, "does not accept speech"),
        ("T02", True, True, "does not accept hand"),
        ("T03", False, True, "requires landmark"),
    ],
)
def test_task_payload_rejects_cross_modal_contract_violations(
    task_code: str,
    hand: bool,
    speech: bool,
    error: str,
):
    task = SimpleNamespace(task_code=task_code, hand="right" if task_code != "T02" else None)
    with pytest.raises(ValueError, match=error):
        _validate_task_payload(task, _submission(hand=hand, speech=speech))


def test_tap_detection_is_invariant_to_frame_order():
    samples = [
        HandSignalSample(timestamp, None, value, True)
        for timestamp, value in [(0, 0.1), (100, 1.0), (200, 0.1), (300, 1.0), (400, 0.1)]
    ]
    expected = detect_tap_events(samples)
    assert detect_tap_events(list(reversed(samples))) == expected


def test_probe_rejects_audio_video_start_skew(monkeypatch: pytest.MonkeyPatch):
    payload = {
        "format": {"duration": "15.0"},
        "streams": [
            {
                "codec_type": "video",
                "avg_frame_rate": "30/1",
                "start_time": "0.0",
                "duration": "15.0",
            },
            {
                "codec_type": "audio",
                "sample_rate": "16000",
                "start_time": "0.250",
                "duration": "14.75",
            },
        ],
    }
    completed = SimpleNamespace(stdout=json.dumps(payload))
    monkeypatch.setattr("services.api.app.services.media.subprocess.run", lambda *a, **k: completed)
    with pytest.raises(ValueError, match="starts differ"):
        probe_media(Path("capture.mp4"))
