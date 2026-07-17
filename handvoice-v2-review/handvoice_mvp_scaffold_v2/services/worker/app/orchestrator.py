"""Archived future-processing contract.

Not invoked by the competition MVP. Retained only as a typed design note for a
future validated asynchronous pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Stage(StrEnum):
    MEDIA_PROBE = "media_probe"
    MEASUREMENT_ANALYSIS = "measurement_analysis"


@dataclass(frozen=True, slots=True)
class WorkItem:
    task_instance_id: str
    storage_key: str
    stage: Stage
    configuration_hash: str


PROCESSING_ORDER = (Stage.MEDIA_PROBE, Stage.MEASUREMENT_ANALYSIS)
