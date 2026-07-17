from pipelines.common.contracts import Modality, TimestampedEvent
from pipelines.coupling.events import (
    calculate_event_coupling,
    match_events_one_to_one,
    permutation_null_coincidence,
)


def e(event_id: str, modality: Modality, at: int) -> TimestampedEvent:
    return TimestampedEvent(event_id, modality, "disruption", at)


def test_one_to_one_matching_prevents_double_counting():
    left = [e("m1", Modality.MOTOR, 1000), e("m2", Modality.MOTOR, 1060)]
    right = [e("s1", Modality.SPEECH, 1030)]
    matches = match_events_one_to_one(left, right, window_ms=100)
    assert len(matches) == 1


def test_matching_maximizes_cardinality_before_minimizing_lag():
    # Greedy nearest-neighbour chooses m2-s1 (lag 1) and leaves only one match.
    # The global optimum chooses m1-s1 and m2-s2, producing two valid matches.
    left = [e("m1", Modality.MOTOR, 0), e("m2", Modality.MOTOR, 4)]
    right = [e("s1", Modality.SPEECH, 3), e("s2", Modality.SPEECH, 7)]
    matches = match_events_one_to_one(left, right, window_ms=4)
    assert {(match.left_event_id, match.right_event_id) for match in matches} == {
        ("m1", "s1"),
        ("m2", "s2"),
    }


def test_equal_cardinality_uses_minimum_total_lag():
    left = [e("m1", Modality.MOTOR, 100), e("m2", Modality.MOTOR, 300)]
    right = [e("s1", Modality.SPEECH, 90), e("s2", Modality.SPEECH, 310)]
    matches = match_events_one_to_one(left, right, window_ms=250)
    assert [match.lag_ms for match in matches] == [-10, 10]


def test_bidirectional_probabilities_and_union_rate():
    left = [e("m1", Modality.MOTOR, 1000), e("m2", Modality.MOTOR, 3000)]
    right = [e("s1", Modality.SPEECH, 1100), e("s2", Modality.SPEECH, 8000)]
    result = calculate_event_coupling(left, right, window_ms=200)
    assert result.matched_count == 1
    assert result.probability_right_given_left == 0.5
    assert result.probability_left_given_right == 0.5
    assert result.event_coincidence_rate == 1 / 3


def test_permutation_null_is_reproducible():
    left = [e("m1", Modality.MOTOR, 1000), e("m2", Modality.MOTOR, 5000)]
    right = [e("s1", Modality.SPEECH, 1100), e("s2", Modality.SPEECH, 5100)]
    first = permutation_null_coincidence(
        left, right, duration_ms=10000, window_ms=200, permutations=20, seed=42
    )
    second = permutation_null_coincidence(
        left, right, duration_ms=10000, window_ms=200, permutations=20, seed=42
    )
    assert first == second
    assert len(first) == 20
