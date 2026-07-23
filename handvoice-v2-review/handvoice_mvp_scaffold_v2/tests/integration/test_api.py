# ruff: noqa: E402

import hashlib
import math
import os
from pathlib import Path
import shutil
import subprocess
from uuid import UUID, uuid4

TEST_OPERATOR_KEY = "test-operator-key-with-at-least-32-bytes"

os.environ["HANDVOICE_DATABASE_URL"] = "sqlite:///./test_handvoice.db"
os.environ["HANDVOICE_AUTO_CREATE_SCHEMA"] = "true"
os.environ["HANDVOICE_PROTOCOL_PATH"] = "configs/protocol.v1.yaml"
os.environ["HANDVOICE_STORAGE_ROOT"] = ".test_storage"
# Seeds the first operator on app startup; the API validates keys against the
# operators table, so this key must be presented on every authenticated request.
os.environ["HANDVOICE_BOOTSTRAP_KEY"] = TEST_OPERATOR_KEY

from fastapi.testclient import TestClient
import pytest

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.app.db.base import Base
from services.api.app.db.session import engine
from services.api.app.main import app
from services.api.app.models.entities import Event, Feature, Recording, TaskInstance
from services.api.app.services.media import MediaCleanupError

HEADERS = {"Authorization": f"Bearer {TEST_OPERATOR_KEY}"}
LEGACY_HEADERS = {"X-HandVoice-API-Key": TEST_OPERATOR_KEY}
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
        "-af",
        "volume=0:enable='gte(mod(t,0.30),0.16)'",
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


def _landmark_frames(period_ms: int, *, frame_step_ms: int = 33) -> list[dict]:
    frames: list[dict] = []
    for timestamp in range(0, 10001, frame_step_ms):
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


def _uploaded_submission(
    client: TestClient,
    *,
    period_ms: int | None,
    ddk_step_ms: int | None,
) -> dict:
    upload = client.post(
        "/v1/media",
        headers=HEADERS,
        files={"file": ("capture.mp4", MEDIA.read_bytes(), "video/mp4")},
    )
    assert upload.status_code == 201
    payload = _submission(period_ms=period_ms, ddk_step_ms=ddk_step_ms)
    payload.update(
        storage_key=upload.json()["storage_key"],
        sha256=upload.json()["sha256"],
    )
    return payload


def test_api_requires_key():
    with TestClient(app) as client:
        response = client.post("/v1/participants", json={"study_id": "HV-PILOT-001"})
        assert response.status_code == 401


def test_unknown_operator_key_is_rejected():
    with TestClient(app) as client:
        response = client.post(
            "/v1/participants",
            headers={"Authorization": "Bearer not-a-real-operator-key"},
            json={"study_id": "HV-PILOT-001"},
        )
        assert response.status_code == 401


def test_legacy_api_key_header_still_authenticates():
    with TestClient(app) as client:
        response = client.post(
            "/v1/participants",
            headers=LEGACY_HEADERS,
            json={"study_id": "HV-PILOT-001", "external_reference": "legacy-header-demo"},
        )
        assert response.status_code == 201


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


def test_hard_deletion_requires_confirmation_and_removes_participant():
    with TestClient(app) as client:
        participant = client.post(
            "/v1/participants",
            headers=HEADERS,
            json={
                "study_id": "HV-PILOT-001",
                "external_reference": "confirmed-hard-delete",
            },
        ).json()
        refused = client.delete(
            f"/v1/participants/{participant['id']}",
            headers=HEADERS,
        )
        assert refused.status_code == 422

        deleted = client.delete(
            f"/v1/participants/{participant['id']}?confirm=true",
            headers=HEADERS,
        )
        assert deleted.status_code == 200
        assert deleted.json()["participant_retained_as_withdrawn"] is False


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
                json=_uploaded_submission(client, period_ms=500, ddk_step_ms=None),
            ),
            client.post(
                f"/v1/task-instances/{tasks['T02']['id']}/measure",
                headers=HEADERS,
                json=_uploaded_submission(client, period_ms=None, ddk_step_ms=300),
            ),
            client.post(
                f"/v1/task-instances/{tasks['T03']['id']}/measure",
                headers=HEADERS,
                json=_uploaded_submission(client, period_ms=650, ddk_step_ms=360),
            ),
        ]
        assert [response.status_code for response in responses] == [201, 201, 201]
        assert [response.json()["quality_decision"] for response in responses] == [
            "accept",
            "accept",
            "accept",
        ]

        report = client.get(f"/v1/sessions/{body['id']}/report", headers=HEADERS)
        assert report.status_code == 200
        report_body = report.json()
        assert report_body["analyzed_task_count"] == 3
        assert report_body["metrics"]["motor_rate_dtc_percent"] > 0
        assert report_body["metrics"]["speech_rate_dtc_percent"] > 0
        assert report_body["exploratory_coupling"]["event_coincidence_rate"] is not None
        assert "no diagnosis" in report_body["note"].lower()
        assert "exploratory and unvalidated" in report_body["note"].lower()

        # Sequence-effect and confound features are computed and persisted for T01.
        with Session(engine) as db:
            t01_feature_rows = list(
                db.execute(
                    select(Feature.feature_name, Feature.status)
                    .join(TaskInstance, Feature.task_instance_id == TaskInstance.id)
                    .where(TaskInstance.id == UUID(tasks["T01"]["id"]))
                ).all()
            )
            t01_features = {name for name, _ in t01_feature_rows}
            t01_statuses = dict(t01_feature_rows)
        assert "amplitude_decrement_slope" in t01_features
        assert "halt_count" in t01_features
        assert "achieved_frame_rate_hz" in t01_features
        assert t01_statuses["amplitude_decrement_slope"] == "exploratory_unvalidated"

        # Acoustic voice features are decoded from the waveform and persisted for
        # the speech-only task even though it supplied its own DDK annotations.
        with Session(engine) as db:
            t02_feature_rows = list(
                db.execute(
                    select(Feature.feature_name, Feature.status)
                    .join(TaskInstance, Feature.task_instance_id == TaskInstance.id)
                    .where(TaskInstance.id == UUID(tasks["T02"]["id"]))
                ).all()
            )
            t02_features = {name for name, _ in t02_feature_rows}
            t02_statuses = dict(t02_feature_rows)
        assert "mean_f0_hz" in t02_features
        assert "jitter_local_percent" in t02_features
        assert "mean_hnr_db" in t02_features
        # DDK temporal fine-structure features are persisted for the speech task.
        assert "ddk_ioi_mean_ms" in t02_features
        assert "ddk_rate_variance_hz2" in t02_features
        assert "ddk_rate_decrement_slope" in t02_features
        assert t02_statuses["ddk_rate_hz"] == "exploratory_unvalidated"
        assert t02_statuses["mean_f0_hz"] == "exploratory_unvalidated"

        visualization = client.get(
            f"/v1/sessions/{body['id']}/visualization", headers=HEADERS
        )
        assert visualization.status_code == 200
        assert "Synchronized motor and speech events" in visualization.text
        assert "Event timeline data" in visualization.text
        assert '<table><caption>Events in timestamp order</caption>' in visualization.text
        assert "Hand tap" in visualization.text
        assert "Candidate acoustic onset (unvalidated)" in visualization.text

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


def test_rejected_capture_is_atomic_removed_and_can_be_retried():
    with TestClient(app) as client:
        participant = client.post(
            "/v1/participants",
            headers=HEADERS,
            json={"study_id": "HV-PILOT-001", "external_reference": "quality-retry"},
        ).json()
        session = client.post(
            "/v1/sessions",
            headers=HEADERS,
            json={"participant_id": participant["id"], "protocol_version": "1.1.0"},
        ).json()
        task = next(task for task in session["tasks"] if task["task_code"] == "T01")

        wrong_hand_upload = client.post(
            "/v1/media",
            headers=HEADERS,
            files={"file": ("wrong-hand.mp4", MEDIA.read_bytes(), "video/mp4")},
        ).json()
        wrong_hand_payload = _submission(period_ms=500, ddk_step_ms=None)
        wrong_hand_payload.update(
            storage_key=wrong_hand_upload["storage_key"],
            sha256=wrong_hand_upload["sha256"],
        )
        for frame in wrong_hand_payload["landmark_frames"]:
            frame["handedness"] = "left"
        wrong_hand = client.post(
            f"/v1/task-instances/{task['id']}/measure",
            headers=HEADERS,
            json=wrong_hand_payload,
        )
        assert wrong_hand.status_code == 201
        assert wrong_hand.json()["quality_decision"] == "retry"
        assert "wrong_hand" in wrong_hand.json()["reason_codes"]
        assert wrong_hand.json()["recording_id"] is None
        assert not (STORAGE / wrong_hand_upload["storage_key"]).exists()

        review_upload = client.post(
            "/v1/media",
            headers=HEADERS,
            files={"file": ("review.mp4", MEDIA.read_bytes(), "video/mp4")},
        ).json()
        review_payload = _submission(period_ms=500, ddk_step_ms=None)
        review_payload.update(
            storage_key=review_upload["storage_key"], sha256=review_upload["sha256"]
        )
        review_payload["landmark_frames"] = _landmark_frames(500, frame_step_ms=45)
        review = client.post(
            f"/v1/task-instances/{task['id']}/measure",
            headers=HEADERS,
            json=review_payload,
        )
        assert review.status_code == 201
        assert review.json()["quality_decision"] == "review_needed"
        assert review.json()["recording_id"] is None
        assert not (STORAGE / review_upload["storage_key"]).exists()

        upload = client.post(
            "/v1/media",
            headers=HEADERS,
            files={"file": ("rejected.mp4", MEDIA.read_bytes(), "video/mp4")},
        ).json()
        rejected_payload = _submission(period_ms=500, ddk_step_ms=None)
        rejected_payload.update(storage_key=upload["storage_key"], sha256=upload["sha256"])
        rejected_payload["landmark_frames"] = _landmark_frames(500, frame_step_ms=50)
        rejected = client.post(
            f"/v1/task-instances/{task['id']}/measure",
            headers=HEADERS,
            json=rejected_payload,
        )
        assert rejected.status_code == 201
        assert rejected.json()["recording_id"] is None
        assert rejected.json()["quality_decision"] == "retry"
        assert "low_frame_rate" in rejected.json()["reason_codes"]
        assert not (STORAGE / upload["storage_key"]).exists()

        with Session(engine) as db:
            task_id = UUID(task["id"])
            assert db.scalar(select(TaskInstance.status).where(TaskInstance.id == task_id)) == "pending"
            assert db.scalar(select(Feature.id).where(Feature.task_instance_id == task_id)) is None
            assert db.scalar(select(Event.id).where(Event.task_instance_id == task_id)) is None
            assert db.scalar(select(Recording.id).where(Recording.task_instance_id == task_id)) is None

        retry_upload = client.post(
            "/v1/media",
            headers=HEADERS,
            files={"file": ("retry.mp4", MEDIA.read_bytes(), "video/mp4")},
        ).json()
        retry_payload = _submission(period_ms=500, ddk_step_ms=None)
        retry_payload.update(storage_key=retry_upload["storage_key"], sha256=retry_upload["sha256"])
        accepted = client.post(
            f"/v1/task-instances/{task['id']}/measure",
            headers=HEADERS,
            json=retry_payload,
        )
        assert accepted.status_code == 201
        assert accepted.json()["quality_decision"] == "accept"
        assert accepted.json()["recording_id"] is not None

        same_request_retry = client.post(
            f"/v1/task-instances/{task['id']}/measure",
            headers=HEADERS,
            json=retry_payload,
        )
        assert same_request_retry.status_code == 201
        assert same_request_retry.json()["recording_id"] == accepted.json()["recording_id"]
        assert same_request_retry.json()["measured_quality"] == accepted.json()["measured_quality"]

        duplicate_upload = client.post(
            "/v1/media",
            headers=HEADERS,
            files={"file": ("duplicate.mp4", MEDIA.read_bytes(), "video/mp4")},
        ).json()
        duplicate_payload = dict(retry_payload)
        duplicate_payload.update(
            storage_key=duplicate_upload["storage_key"],
            sha256=duplicate_upload["sha256"],
        )
        duplicate_retry = client.post(
            f"/v1/task-instances/{task['id']}/measure",
            headers=HEADERS,
            json=duplicate_payload,
        )
        assert duplicate_retry.status_code == 201
        assert duplicate_retry.json()["measured_quality"] == accepted.json()["measured_quality"]
        assert not (STORAGE / duplicate_upload["storage_key"]).exists()


def test_nonexistent_task_discards_pending_upload():
    with TestClient(app) as client:
        upload = client.post(
            "/v1/media",
            headers=HEADERS,
            files={"file": ("orphan.mp4", MEDIA.read_bytes(), "video/mp4")},
        ).json()
        payload = _submission(period_ms=500, ddk_step_ms=None)
        payload.update(storage_key=upload["storage_key"], sha256=upload["sha256"])

        response = client.post(
            f"/v1/task-instances/{uuid4()}/measure",
            headers=HEADERS,
            json=payload,
        )

        assert response.status_code == 404
        assert not (STORAGE / upload["storage_key"]).exists()


def test_cleanup_failure_is_structured_and_never_accepts_task(
    monkeypatch: pytest.MonkeyPatch,
):
    with TestClient(app) as client:
        participant = client.post(
            "/v1/participants",
            headers=HEADERS,
            json={"study_id": "HV-PILOT-001", "external_reference": "cleanup-failure"},
        ).json()
        session = client.post(
            "/v1/sessions",
            headers=HEADERS,
            json={"participant_id": participant["id"], "protocol_version": "1.1.0"},
        ).json()
        task = next(task for task in session["tasks"] if task["task_code"] == "T01")
        upload = client.post(
            "/v1/media",
            headers=HEADERS,
            files={"file": ("locked.mp4", MEDIA.read_bytes(), "video/mp4")},
        ).json()
        payload = _submission(period_ms=500, ddk_step_ms=None)
        payload.update(storage_key=upload["storage_key"], sha256=upload["sha256"])
        payload["landmark_frames"] = _landmark_frames(500, frame_step_ms=50)

        def fail_cleanup(*args, **kwargs):
            raise MediaCleanupError("locked")

        monkeypatch.setattr(
            "services.api.app.services.measurement.discard_uploaded_media",
            fail_cleanup,
        )
        response = client.post(
            f"/v1/task-instances/{task['id']}/measure",
            headers=HEADERS,
            json=payload,
        )

        assert response.status_code == 500
        assert response.json()["detail"]["code"] == "privacy_cleanup_failed"
        with Session(engine) as db:
            task_id = UUID(task["id"])
            assert db.scalar(select(TaskInstance.status).where(TaskInstance.id == task_id)) == "pending"
            assert db.scalar(select(Recording.id).where(Recording.task_instance_id == task_id)) is None
