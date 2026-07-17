from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FrameValidity(StrEnum):
    VALID = "valid"
    INTERPOLATED_SHORT_GAP = "interpolated_short_gap"
    LOW_CONFIDENCE = "low_confidence"
    MISSING_HAND = "missing_hand"
    OCCLUDED = "occluded"
    MOTION_BLUR = "motion_blur"
    OUT_OF_GUIDE = "out_of_guide"
    TIMESTAMP_ANOMALY = "timestamp_anomaly"


@dataclass(frozen=True, slots=True)
class LandmarkFrame:
    timestamp_ms: int
    handedness: str
    landmarks_xyz: tuple[tuple[float, float, float], ...]
    median_confidence: float
    validity: FrameValidity

    def __post_init__(self) -> None:
        if len(self.landmarks_xyz) != 21:
            raise ValueError("MediaPipe hand frame must contain 21 landmarks")
