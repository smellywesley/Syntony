from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.api.app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Operator(Base):
    """A clinic/study operator authorized to run captures.

    Replaces the single global API key: each operator (or site) holds its own
    secret, stored only as a SHA-256 hash, scoped to a study and independently
    revocable. Patients never hold or see an operator key.
    """

    __tablename__ = "operators"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    label: Mapped[str] = mapped_column(String(120))
    # NULL study_id means the key is valid for every study (e.g. the bootstrap key).
    study_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ParticipantStatus(StrEnum):
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"


class SessionStatus(StrEnum):
    CREATED = "created"
    CAPTURING = "capturing"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETE = "complete"
    INVALID = "invalid"


class TaskStatus(StrEnum):
    PENDING = "pending"
    CAPTURED = "captured"
    PROCESSING = "processing"
    COMPLETE = "complete"
    INVALID = "invalid"


class Participant(Base):
    __tablename__ = "participants"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    study_id: Mapped[str] = mapped_column(String(100), index=True)
    external_reference: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    status: Mapped[str] = mapped_column(String(30), default=ParticipantStatus.ACTIVE.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sessions: Mapped[list["AssessmentSession"]] = relationship(back_populates="participant", cascade="all, delete-orphan")


class AssessmentSession(Base):
    __tablename__ = "assessment_sessions"
    __table_args__ = (UniqueConstraint("participant_id", "session_number", name="uq_participant_session_number"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    participant_id: Mapped[UUID] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), index=True)
    protocol_version: Mapped[str] = mapped_column(String(50))
    sequence_id: Mapped[str] = mapped_column(String(10))
    session_number: Mapped[int] = mapped_column(Integer)
    context_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default=SessionStatus.CREATED.value)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    participant: Mapped[Participant] = relationship(back_populates="sessions")
    tasks: Mapped[list["TaskInstance"]] = relationship(back_populates="session", cascade="all, delete-orphan", order_by="TaskInstance.order_index")


class TaskInstance(Base):
    __tablename__ = "task_instances"
    __table_args__ = (UniqueConstraint("session_id", "task_code", "repetition", name="uq_session_task_repetition"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("assessment_sessions.id", ondelete="CASCADE"), index=True)
    task_code: Mapped[str] = mapped_column(String(10), index=True)
    task_name: Mapped[str] = mapped_column(String(100))
    condition: Mapped[str] = mapped_column(String(20))
    hand: Mapped[str | None] = mapped_column(String(10), nullable=True)
    speech_task: Mapped[str | None] = mapped_column(String(50), nullable=True)
    repetition: Mapped[int] = mapped_column(Integer)
    order_index: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default=TaskStatus.PENDING.value)
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    session: Mapped[AssessmentSession] = relationship(back_populates="tasks")
    recordings: Mapped[list["Recording"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    features: Mapped[list["Feature"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    events: Mapped[list["Event"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class Recording(Base):
    __tablename__ = "recordings"
    # One accepted recording per task instance; repeats get their own task instance.
    # The constraint closes the check-then-insert race in submit_measurement.
    __table_args__ = (UniqueConstraint("task_instance_id", name="uq_recording_task_instance"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_instance_id: Mapped[UUID] = mapped_column(ForeignKey("task_instances.id", ondelete="CASCADE"))
    object_uri: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    duration_ms: Mapped[int] = mapped_column(Integer)
    video_fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    audio_sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    task: Mapped[TaskInstance] = relationship(back_populates="recordings")


class Feature(Base):
    __tablename__ = "features"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_instance_id: Mapped[UUID] = mapped_column(ForeignKey("task_instances.id", ondelete="CASCADE"), index=True)
    modality: Mapped[str] = mapped_column(String(30), index=True)
    feature_name: Mapped[str] = mapped_column(String(150), index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(50))
    window_start_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    window_end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="accepted")
    algorithm_version: Mapped[str] = mapped_column(String(100))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    task: Mapped[TaskInstance] = relationship(back_populates="features")


class Event(Base):
    __tablename__ = "events"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_instance_id: Mapped[UUID] = mapped_column(ForeignKey("task_instances.id", ondelete="CASCADE"), index=True)
    modality: Mapped[str] = mapped_column(String(30), index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    algorithm_version: Mapped[str] = mapped_column(String(100))
    task: Mapped[TaskInstance] = relationship(back_populates="events")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[str] = mapped_column(String(100))
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
