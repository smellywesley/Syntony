from __future__ import annotations

from dataclasses import dataclass
from math import acos, isfinite, sqrt
from statistics import median
from typing import Sequence

from pipelines.video.contracts import FrameValidity, LandmarkFrame


@dataclass(frozen=True, slots=True)
class HandSignalSample:
    timestamp_ms: int
    thumb_index_angle_rad: float | None
    normalized_thumb_index_distance: float | None
    valid: bool
    quality_reason: str | None = None


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != 3 or len(b) != 3:
        raise ValueError("landmarks must be three-dimensional")
    return sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b, strict=True)))


def _angle(a: Sequence[float], vertex: Sequence[float], b: Sequence[float]) -> float | None:
    if len(a) != 3 or len(vertex) != 3 or len(b) != 3:
        return None
    va = tuple(float(x) - float(y) for x, y in zip(a, vertex, strict=True))
    vb = tuple(float(x) - float(y) for x, y in zip(b, vertex, strict=True))
    na = sqrt(sum(x * x for x in va))
    nb = sqrt(sum(x * x for x in vb))
    if na <= 0 or nb <= 0:
        return None
    cosine = max(-1.0, min(1.0, sum(x * y for x, y in zip(va, vb, strict=True)) / (na * nb)))
    return acos(cosine)


def derive_hand_signal(frames: list[LandmarkFrame]) -> list[HandSignalSample]:
    samples: list[HandSignalSample] = []
    for frame in frames:
        valid_status = frame.validity in {FrameValidity.VALID, FrameValidity.INTERPOLATED_SHORT_GAP}
        if not valid_status:
            samples.append(HandSignalSample(frame.timestamp_ms, None, None, False, frame.validity.value))
            continue
        landmarks = frame.landmarks_xyz
        if len(landmarks) < 18:
            samples.append(HandSignalSample(frame.timestamp_ms, None, None, False, "malformed_landmark_count"))
            continue
        try:
            wrist = landmarks[0]
            thumb_tip = landmarks[4]
            index_tip = landmarks[8]
            index_mcp = landmarks[5]
            middle_mcp = landmarks[9]
            pinky_mcp = landmarks[17]
            palm_scales = [_distance(wrist, middle_mcp), _distance(index_mcp, pinky_mcp)]
            positive_scales = [scale for scale in palm_scales if isfinite(scale) and scale > 1e-9]
            if not positive_scales:
                samples.append(HandSignalSample(frame.timestamp_ms, None, None, False, "invalid_palm_scale"))
                continue
            palm_scale = median(positive_scales)
            angle = _angle(thumb_tip, wrist, index_tip)
            normalized_distance = _distance(thumb_tip, index_tip) / palm_scale
            if angle is None or not isfinite(normalized_distance):
                samples.append(HandSignalSample(frame.timestamp_ms, None, None, False, "non_finite_geometry"))
                continue
            samples.append(
                HandSignalSample(
                    timestamp_ms=frame.timestamp_ms,
                    thumb_index_angle_rad=angle,
                    normalized_thumb_index_distance=normalized_distance,
                    valid=True,
                )
            )
        except (IndexError, TypeError, ValueError, ZeroDivisionError):
            samples.append(HandSignalSample(frame.timestamp_ms, None, None, False, "malformed_landmarks"))
    return samples
