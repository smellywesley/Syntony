from __future__ import annotations

from dataclasses import dataclass
from math import acos, sqrt
from statistics import median

from pipelines.video.contracts import FrameValidity, LandmarkFrame


@dataclass(frozen=True, slots=True)
class HandSignalSample:
    timestamp_ms: int
    thumb_index_angle_rad: float | None
    normalized_thumb_index_distance: float | None
    valid: bool


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


def _angle(a: tuple[float, float, float], vertex: tuple[float, float, float], b: tuple[float, float, float]) -> float | None:
    va = tuple(x - y for x, y in zip(a, vertex, strict=True))
    vb = tuple(x - y for x, y in zip(b, vertex, strict=True))
    na = sqrt(sum(x * x for x in va))
    nb = sqrt(sum(x * x for x in vb))
    if na == 0 or nb == 0:
        return None
    cosine = max(-1.0, min(1.0, sum(x * y for x, y in zip(va, vb, strict=True)) / (na * nb)))
    return acos(cosine)


def derive_hand_signal(frames: list[LandmarkFrame]) -> list[HandSignalSample]:
    samples: list[HandSignalSample] = []
    for frame in frames:
        valid = frame.validity in {FrameValidity.VALID, FrameValidity.INTERPOLATED_SHORT_GAP}
        if not valid:
            samples.append(HandSignalSample(frame.timestamp_ms, None, None, False))
            continue
        wrist = frame.landmarks_xyz[0]
        thumb_tip = frame.landmarks_xyz[4]
        index_tip = frame.landmarks_xyz[8]
        index_mcp = frame.landmarks_xyz[5]
        middle_mcp = frame.landmarks_xyz[9]
        pinky_mcp = frame.landmarks_xyz[17]
        palm_scales = [_distance(wrist, middle_mcp), _distance(index_mcp, pinky_mcp)]
        palm_scale = median(scale for scale in palm_scales if scale > 0)
        samples.append(
            HandSignalSample(
                timestamp_ms=frame.timestamp_ms,
                thumb_index_angle_rad=_angle(thumb_tip, wrist, index_tip),
                normalized_thumb_index_distance=_distance(thumb_tip, index_tip) / palm_scale,
                valid=True,
            )
        )
    return samples
