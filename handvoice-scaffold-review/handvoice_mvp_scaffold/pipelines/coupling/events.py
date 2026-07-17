from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Iterable, Sequence

from pipelines.common.contracts import TimestampedEvent


@dataclass(frozen=True, slots=True)
class EventMatch:
    left_event_id: str
    right_event_id: str
    lag_ms: int


@dataclass(frozen=True, slots=True)
class CouplingResult:
    left_count: int
    right_count: int
    matched_count: int
    probability_right_given_left: float | None
    probability_left_given_right: float | None
    event_coincidence_rate: float | None
    matches: tuple[EventMatch, ...]


def match_events_one_to_one(
    left_events: Sequence[TimestampedEvent],
    right_events: Sequence[TimestampedEvent],
    *,
    window_ms: int,
) -> tuple[EventMatch, ...]:
    """Greedy minimum-absolute-lag one-to-one event matching."""
    if window_ms < 0:
        raise ValueError("window_ms must be non-negative")

    candidates: list[tuple[int, int, int]] = []
    for li, left in enumerate(left_events):
        for ri, right in enumerate(right_events):
            lag = right.start_ms - left.start_ms
            if abs(lag) <= window_ms:
                candidates.append((abs(lag), li, ri))

    candidates.sort(key=lambda row: (row[0], left_events[row[1]].start_ms, right_events[row[2]].start_ms))
    used_left: set[int] = set()
    used_right: set[int] = set()
    matches: list[EventMatch] = []

    for _, li, ri in candidates:
        if li in used_left or ri in used_right:
            continue
        used_left.add(li)
        used_right.add(ri)
        matches.append(EventMatch(left_events[li].event_id, right_events[ri].event_id, right_events[ri].start_ms - left_events[li].start_ms))

    return tuple(sorted(matches, key=lambda match: match.left_event_id))


def calculate_event_coupling(
    left_events: Sequence[TimestampedEvent],
    right_events: Sequence[TimestampedEvent],
    *,
    window_ms: int,
) -> CouplingResult:
    matches = match_events_one_to_one(left_events, right_events, window_ms=window_ms)
    left_count = len(left_events)
    right_count = len(right_events)
    matched_count = len(matches)
    union_count = left_count + right_count - matched_count
    return CouplingResult(
        left_count=left_count,
        right_count=right_count,
        matched_count=matched_count,
        probability_right_given_left=(matched_count / left_count) if left_count else None,
        probability_left_given_right=(matched_count / right_count) if right_count else None,
        event_coincidence_rate=(matched_count / union_count) if union_count else None,
        matches=matches,
    )


def permutation_null_coincidence(
    left_events: Sequence[TimestampedEvent],
    right_events: Sequence[TimestampedEvent],
    *,
    duration_ms: int,
    window_ms: int,
    permutations: int = 1000,
    seed: int = 7,
) -> list[float]:
    """Circularly shift the right stream and return null coincidence rates."""
    if duration_ms <= 0:
        raise ValueError("duration_ms must be positive")
    if permutations <= 0:
        raise ValueError("permutations must be positive")
    rng = random.Random(seed)
    rates: list[float] = []
    for _ in range(permutations):
        shift = rng.randrange(duration_ms)
        shifted = [
            TimestampedEvent(
                event_id=f"{event.event_id}@{shift}",
                modality=event.modality,
                event_type=event.event_type,
                start_ms=(event.start_ms + shift) % duration_ms,
                end_ms=None if event.end_ms is None else (event.end_ms + shift) % duration_ms,
                confidence=event.confidence,
                metadata=event.metadata,
            )
            for event in right_events
        ]
        result = calculate_event_coupling(left_events, shifted, window_ms=window_ms)
        rates.append(result.event_coincidence_rate or 0.0)
    return rates
