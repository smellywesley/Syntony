from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID


class Modality(StrEnum):
    MOTOR = "motor"
    SPEECH = "speech"
    QUALITY = "quality"
    COUPLING = "coupling"


class FeatureStatus(StrEnum):
    ACCEPTED = "accepted"
    ACCEPTED_WITH_WARNING = "accepted_with_warning"
    UNAVAILABLE = "unavailable"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class TimestampedEvent:
    event_id: str
    modality: Modality
    event_type: str
    start_ms: int
    end_ms: int | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.start_ms < 0:
            raise ValueError("start_ms must be non-negative")
        if self.end_ms is not None and self.end_ms < self.start_ms:
            raise ValueError("end_ms cannot precede start_ms")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class FeatureValue:
    task_instance_id: UUID
    modality: Modality
    name: str
    value: float | None
    unit: str
    status: FeatureStatus
    window_start_ms: int | None = None
    window_end_ms: int | None = None
    quality_score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
