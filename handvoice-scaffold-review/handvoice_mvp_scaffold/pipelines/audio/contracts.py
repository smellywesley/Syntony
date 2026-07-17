from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SpeechTask(StrEnum):
    COUNT_BACKWARDS = "count_backwards"
    DDK_PATAKA = "ddk_pataka"
    SUSTAINED_A = "sustained_a"
    READING = "reading"


@dataclass(frozen=True, slots=True)
class AudioQuality:
    snr_db: float | None
    clipping_fraction: float
    voiced_fraction: float
    dropout_ms: int
    second_speaker_probability: float | None = None
