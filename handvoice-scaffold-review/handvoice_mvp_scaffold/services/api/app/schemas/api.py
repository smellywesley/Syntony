from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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


class SessionCreate(BaseModel):
    participant_id: UUID
    protocol_version: str = "1.0.0"
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


class RecordingComplete(BaseModel):
    object_uri: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    duration_ms: int = Field(ge=1000, le=120000)
    video_fps: float | None = Field(default=None, gt=0, le=240)
    audio_sample_rate: int | None = Field(default=None, ge=8000, le=192000)
    manifest: dict[str, Any] = Field(default_factory=dict)


class HealthRead(BaseModel):
    status: str
    environment: str


class SessionReport(BaseModel):
    session_id: UUID
    status: str
    task_count: int
    captured_task_count: int
    feature_count: int
    event_count: int
    note: str
