from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Stage(StrEnum):
    MEDIA_PROBE = "media_probe"
    TIMELINE_VALIDATION = "timeline_validation"
    VIDEO_FEATURES = "video_features"
    AUDIO_FEATURES = "audio_features"
    DUAL_TASK = "dual_task"
    COUPLING = "coupling"
    LONGITUDINAL = "longitudinal"


@dataclass(frozen=True, slots=True)
class WorkItem:
    task_instance_id: str
    recording_uri: str
    stage: Stage
    configuration_hash: str


PROCESSING_ORDER = (
    Stage.MEDIA_PROBE,
    Stage.TIMELINE_VALIDATION,
    Stage.VIDEO_FEATURES,
    Stage.AUDIO_FEATURES,
    Stage.DUAL_TASK,
    Stage.COUPLING,
    Stage.LONGITUDINAL,
)
