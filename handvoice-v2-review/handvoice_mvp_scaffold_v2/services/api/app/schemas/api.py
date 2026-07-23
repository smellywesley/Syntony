from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ParticipantCreate(BaseModel):
    study_id: str = Field(min_length=1, max_length=100)
    external_reference: str | None = Field(default=None, max_length=255)


class ParticipantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    study_id: str
    external_reference: str | None
    status: str
    created_at: datetime


class PrivacyDeletionRead(BaseModel):
    participant_id: UUID
    deleted_session_count: int
    deleted_recording_count: int
    deleted_media_count: int
    participant_retained_as_withdrawn: bool


class SessionCreate(BaseModel):
    participant_id: UUID
    protocol_version: str = "1.1.0"
    context: dict[str, Any] = Field(default_factory=dict)


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    task_code: str
    task_name: str
    condition: str
    hand: str | None
    speech_task: str | None
    repetition: int
    order_index: int
    status: str


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    participant_id: UUID
    protocol_version: str
    sequence_id: str
    session_number: int
    context_json: dict[str, Any]
    status: str
    started_at: datetime
    completed_at: datetime | None
    tasks: list[TaskRead]


class CaptureManifest(BaseModel):
    protocol_version: Literal["1.1.0"]
    active_start_ms: int = Field(ge=0, le=5000)
    active_end_ms: int = Field(ge=9000, le=15000)
    camera_facing: Literal["front", "rear"]
    capture_app_version: str = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def active_window_is_ten_seconds(self) -> "CaptureManifest":
        if (self.active_start_ms, self.active_end_ms) != (2000, 12000):
            raise ValueError("active window must use the frozen 2000-12000 ms protocol window")
        return self


class IntervalInput(BaseModel):
    start_ms: int = Field(ge=0, le=10000)
    end_ms: int = Field(ge=0, le=10000)

    @model_validator(mode="after")
    def valid_interval(self) -> "IntervalInput":
        if self.end_ms <= self.start_ms:
            raise ValueError("interval end must follow start")
        return self


class LandmarkFrameInput(BaseModel):
    timestamp_ms: int = Field(ge=0, le=10000)
    handedness: Literal["left", "right"]
    landmarks_xyz: list[tuple[float, float, float]] = Field(min_length=21, max_length=21)
    median_confidence: float = Field(ge=0, le=1)
    validity: Literal[
        "valid",
        "interpolated_short_gap",
        "low_confidence",
        "missing_hand",
        "occluded",
        "motion_blur",
        "out_of_guide",
        "timestamp_anomaly",
    ]


class MeasurementSubmission(BaseModel):
    storage_key: str = Field(min_length=1, max_length=500, pattern=r"^[A-Za-z0-9_./-]+$")
    sha256: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    manifest: CaptureManifest
    landmark_frames: list[LandmarkFrameInput] = Field(default_factory=list, max_length=2000)
    voiced_intervals: list[IntervalInput] = Field(default_factory=list, max_length=1000)
    ddk_event_ms: list[int] = Field(default_factory=list, max_length=1000)
    capture_interrupted: bool = False


class MeasurementRead(BaseModel):
    recording_id: UUID | None
    status: Literal["analyzed_synchronously", "capture_not_accepted"]
    quality_decision: Literal["accept", "retry", "review_needed"]
    reason_codes: list[
        Literal[
            "low_frame_rate",
            "low_valid_frame_fraction",
            "hand_out_of_guide",
            "wrong_hand",
            "low_audio_snr",
            "audio_clipping",
            "av_start_offset",
            "audio_decode_failed",
            "speech_not_detected",
            "insufficient_motor_events",
            "insufficient_ddk_events",
            "capture_interrupted",
        ]
    ]
    measured_quality: dict[str, float | None]
    guidance_key: str


class MediaUploadRead(BaseModel):
    storage_key: str
    sha256: str
    size_bytes: int


class RepeatTaskRead(BaseModel):
    task: TaskRead
    reason: str


class HealthRead(BaseModel):
    status: str
    environment: str


class ReadinessRead(BaseModel):
    status: Literal["ready", "not_ready"]
    components: dict[str, bool]


class SessionReport(BaseModel):
    session_id: UUID
    status: str
    task_count: int
    analyzed_task_count: int
    feature_count: int
    event_count: int
    metrics: dict[str, float | None]
    exploratory_coupling: dict[str, float | None]
    note: str
