from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Sequence

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


@dataclass(frozen=True, slots=True)
class _Plan:
    matched_count: int
    total_abs_lag: int
    pairs: tuple[tuple[int, int], ...]


def _better(first: _Plan, second: _Plan) -> _Plan:
    """Choose maximum cardinality, then minimum lag, then deterministic order."""
    first_key = (-first.matched_count, first.total_abs_lag, first.pairs)
    second_key = (-second.matched_count, second.total_abs_lag, second.pairs)
    return first if first_key <= second_key else second


def match_events_one_to_one(
    left_events: Sequence[TimestampedEvent],
    right_events: Sequence[TimestampedEvent],
    *,
    window_ms: int,
) -> tuple[EventMatch, ...]:
    """Return a maximum-cardinality, minimum-total-lag one-to-one matching.

    Events are ordered on a shared time axis. For absolute-lag costs, an optimal
    matching can be chosen without crossing pairs, so dynamic programming over
    the sorted streams yields the global optimum. This avoids the cardinality
    failures possible with greedy nearest-neighbour matching.
    """
    if window_ms < 0:
        raise ValueError("window_ms must be non-negative")

    left = sorted(enumerate(left_events), key=lambda item: (item[1].start_ms, item[1].event_id))
    right = sorted(enumerate(right_events), key=lambda item: (item[1].start_ms, item[1].event_id))
    n, m = len(left), len(right)
    empty = _Plan(0, 0, ())
    dp: list[list[_Plan]] = [[empty for _ in range(m + 1)] for _ in range(n + 1)]

    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            best = _better(dp[i + 1][j], dp[i][j + 1])
            left_event = left[i][1]
            right_event = right[j][1]
            lag = right_event.start_ms - left_event.start_ms
            if abs(lag) <= window_ms:
                tail = dp[i + 1][j + 1]
                matched = _Plan(
                    matched_count=tail.matched_count + 1,
                    total_abs_lag=tail.total_abs_lag + abs(lag),
                    pairs=((i, j),) + tail.pairs,
                )
                best = _better(best, matched)
            dp[i][j] = best

    matches = [
        EventMatch(
            left_event_id=left[i][1].event_id,
            right_event_id=right[j][1].event_id,
            lag_ms=right[j][1].start_ms - left[i][1].start_ms,
        )
        for i, j in dp[0][0].pairs
    ]
    return tuple(matches)


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
