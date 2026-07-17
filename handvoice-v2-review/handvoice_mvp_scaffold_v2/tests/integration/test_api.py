import hashlib
import math
import os
from pathlib import Path
import shutil
import subprocess

os.environ["HANDVOICE_DATABASE_URL"] = "sqlite:///./test_handvoice.db"
os.environ["HANDVOICE_AUTO_CREATE_SCHEMA"] = "true"
os.environ["HANDVOICE_PROTOCOL_PATH"] = "configs/protocol.v1.yaml"
os.environ["HANDVOICE_STORAGE_ROOT"] = ".test_storage"
os.environ["HANDVOICE_API_KEY"] = "test-api-key"

from fastapi.testclient import TestClient

from services.api.app.db.base import Base
from services.api.app.db.session import engine
from services.api.app.main import app

HEADERS = {"X-HandVoice-API-Key": "test-api-key"}
STORAGE = Path(".test_storage")
MEDIA = STORAGE / "capture.mp4"


def _make_media() -> None:
    STORAGE.mkdir(exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=160x120:r=30:d=15",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=16000:duration=15",
        "-shortest",
        "-c:v",
        "mpeg4",
        "-c:a",
        "aac",
        str(MEDIA),
    ]
    subprocess.run(command, check=True)


def setup_module():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _make_media()


def teardown_module():
    Base.metadata.drop_all(bind=engine)
    engine.dispose()  # release the SQLite file handle so Windows allows the unlink
    Path("test_handvoice.db").unlink(missing_ok=True)
    shutil.rmtree(STORAGE, ignore_errors=True)


def _landmark_frames(period_ms: int) -> list[dict]:
    frames: list[dict] = []
    for timestamp in range(0, 10001, 100):
        phase = 2 * math.pi * timestamp / period_ms
        opening = 0.25 + 0.20 * (1 + math.sin(phase))
        landmarks = [[0.0, 0.0, 0.0] for _ in range(21)]
        landmarks[0] = [0.0, 0.0, 0.0]
        landmarks[4] = [0.2, 0.0, 0.0]
        landmarks[5] = [-0.5, 0.5, 0.0]
        landmarks[8] = [0.2 + opening, 0.1, 0.0]
        landmarks[9] = [0.0, 1.0, 0.0]
        landmarks[17] = [0.5, 0.5, 0.0]
        frames.append(
            {
                "timestamp_ms": timestamp,
                "handedness": "right",
                "landmarks_xyz": landmarks,
                "median_confidence": 0.95,
                "validity": "valid",
            }
        )
    return frames


def _submission(*, period_ms: int | None, ddk_step_ms: int | None) -> dict:
    digest = hashlib.sha256(MEDIA.read_bytes()).hexdigest()
    return {
        "storage_key": "capture.mp4",
        "sha256": digest,
        "manifest": {
            "protocol_version": "1.1.0",
            "active_start_ms": 2000,
            "active_end_ms": 12000,
            "camera_facing": "front",
            "capture_app_version": "test-0.1",
        },
        "landmark_frames": [] if period_ms is None else _landmark_frames(period_ms),
        "voiced_intervals": [] if ddk_step_ms is None else [
            {"start_ms": 100, "end_ms": 4800},
            {"start_ms": 4700, "end_ms": 9900},
        ],
        "ddk_event_ms": [] if ddk_step_ms is None else list(range(200, 9800, ddk_step_ms)),
    }


def test_api_requires_key():
    with TestClient(app) as client:
        response = client.post("/v1/participants", json={"study_id": "HV-PILOT-001"})
        assert response.status_code == 401


def test_media_upload_returns_generated_contained_key():
    with TestClient(app) as client:
        response = client.post(
            "/v1/media",
            headers=HEADERS,
            files={"file": ("../../capture.mp4", MEDIA.read_bytes(), "video/mp4")},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["storage_key"].startswith("incoming/")
        assert ".." not in body["storage_key"]
        assert (STORAGE / body["storage_key"]).is_file()


def test_three_task_synchronous_measurement_path():
    with TestClient(app) as client:
        participant_response = client.post(
            "/v1/participants",
            headers=HEADERS,
            json={"study_id": "HV-PILOT-001", "external_reference": "demo-001"},
        )
        assert participant_response.status_code == 201
        participant_id = participant_response.json()["id"]

        session_response = client.post(
            "/v1/sessions",
            headers=HEADERS,
            json={
                "participant_id": participant_id,
                "protocol_version": "1.1.0",
                "context": {"fatigue_0_10": 3},
            },
        )
        assert session_response.status_code == 201
        body = session_response.json()
        assert len(body["tasks"]) == 3
        assert body["sequence_id"] in {"A", "B"}
        tasks = {task["task_code"]: task for task in body["tasks"]}

        second_session = client.post(
            "/v1/sessions",
            headers=HEADERS,
            json={"participant_id": participant_id, "protocol_version": "1.1.0"},
        )
        assert second_session.status_code == 201
        assert second_session.json()["session_number"] == 2
        assert second_session.json()["sequence_id"] != body["sequence_id"]

        responses = [
            client.post(
                f"/v1/task-instances/{tasks['T01']['id']}/measure",
                headers=HEADERS,
                json=_submission(period_ms=500, ddk_step_ms=None),
            ),
            client.post(
                f"/v1/task-instances/{tasks['T02']['id']}/measure",
                headers=HEADERS,
                json=_submission(period_ms=None, ddk_step_ms=300),
            ),
            client.post(
                f"/v1/task-instances/{tasks['T03']['id']}/measure",
                headers=HEADERS,
                json=_submission(period_ms=650, ddk_step_ms=360),
            ),
        ]
        assert [response.status_code for response in responses] == [201, 201, 201]

        report = client.get(f"/v1/sessions/{body['id']}/report", headers=HEADERS)
        assert report.status_code == 200
        report_body = report.json()
        assert report_body["analyzed_task_count"] == 3
        assert report_body["metrics"]["motor_rate_dtc_percent"] > 0
        assert report_body["metrics"]["speech_rate_dtc_percent"] > 0
        assert report_body["exploratory_coupling"]["event_coincidence_rate"] is not None
        assert "no diagnosis" in report_body["note"].lower()

        visualization = client.get(
            f"/v1/sessions/{body['id']}/visualization", headers=HEADERS
        )
        assert visualization.status_code == 200
        assert "Synchronized motor and speech events" in visualization.text

        repeat = client.post(
            f"/v1/task-instances/{tasks['T01']['id']}/repeat", headers=HEADERS
        )
        assert repeat.status_code == 201
        assert repeat.json()["task"]["repetition"] == 2


def test_storage_escape_is_rejected():
    with TestClient(app) as client:
        participant = client.post(
            "/v1/participants",
            headers=HEADERS,
            json={"study_id": "HV-PILOT-001", "external_reference": "demo-escape"},
        ).json()
        session = client.post(
            "/v1/sessions",
            headers=HEADERS,
            json={"participant_id": participant["id"], "protocol_version": "1.1.0"},
        ).json()
        task = next(task for task in session["tasks"] if task["task_code"] == "T01")
        payload = _submission(period_ms=500, ddk_step_ms=None)
        payload["storage_key"] = "../capture.mp4"
        response = client.post(
            f"/v1/task-instances/{task['id']}/measure",
            headers=HEADERS,
            json=payload,
        )
        assert response.status_code == 422
