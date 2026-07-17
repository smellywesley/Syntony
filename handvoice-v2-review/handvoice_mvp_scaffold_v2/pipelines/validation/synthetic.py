from __future__ import annotations

from dataclasses import asdict, dataclass
from math import exp
from random import Random
from statistics import mean

from pipelines.dual_task.cost import CostStatus, Orientation, calculate_dual_task_cost
from pipelines.measurement.core import detect_tap_events
from pipelines.video.extractor import HandSignalSample


@dataclass(frozen=True, slots=True)
class PerturbationScenario:
    name: str
    frame_rate_hz: int
    timestamp_jitter_ms: int = 0
    noise_sd: float = 0.0
    dropout_probability: float = 0.0
    reverse_submission_order: bool = False
    duplicate_timestamps: bool = False


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    name: str
    replicates: int
    truth_events: int
    detected_events: int
    matched_events: int
    recall: float
    precision: float
    timing_mae_ms: float | None
    count_error_rate: float
    passed: bool


SCENARIOS = (
    PerturbationScenario("clean_30fps", 30),
    PerturbationScenario("low_rate_15fps", 15),
    PerturbationScenario("jitter_noise", 30, timestamp_jitter_ms=10, noise_sd=0.03),
    PerturbationScenario("ten_percent_dropout", 30, timestamp_jitter_ms=8, noise_sd=0.02, dropout_probability=0.10),
    PerturbationScenario(
        "reversed_with_duplicates",
        30,
        timestamp_jitter_ms=5,
        noise_sd=0.01,
        reverse_submission_order=True,
        duplicate_timestamps=True,
    ),
)


def _truth_events(*, duration_ms: int = 10_000, interval_ms: int = 500) -> list[int]:
    return list(range(interval_ms, duration_ms, interval_ms))


def _synthetic_hand_samples(
    scenario: PerturbationScenario,
    *,
    seed: int,
    duration_ms: int = 10_000,
) -> list[HandSignalSample]:
    rng = Random(seed)
    step_ms = 1000.0 / scenario.frame_rate_hz
    truth = _truth_events(duration_ms=duration_ms)
    samples: list[HandSignalSample] = []
    frame_index = 0
    while True:
        nominal_ms = round(frame_index * step_ms)
        if nominal_ms > duration_ms:
            break
        frame_index += 1
        if rng.random() < scenario.dropout_probability:
            continue
        timestamp_ms = nominal_ms + rng.randint(
            -scenario.timestamp_jitter_ms,
            scenario.timestamp_jitter_ms,
        )
        timestamp_ms = min(duration_ms, max(0, timestamp_ms))
        pulse = max(exp(-0.5 * ((nominal_ms - event_ms) / 55.0) ** 2) for event_ms in truth)
        value = 0.22 + 0.78 * pulse + rng.gauss(0.0, scenario.noise_sd)
        sample = HandSignalSample(timestamp_ms, None, value, True)
        samples.append(sample)
        if scenario.duplicate_timestamps and frame_index % 19 == 0:
            samples.append(HandSignalSample(timestamp_ms, None, value - 0.05, True))
    if scenario.reverse_submission_order:
        samples.reverse()
    return samples


def _match_with_tolerance(
    truth: list[int],
    detected: list[int],
    *,
    tolerance_ms: int = 80,
) -> tuple[int, list[int]]:
    unmatched = set(range(len(detected)))
    errors: list[int] = []
    for expected_ms in truth:
        candidates = [
            (abs(detected[index] - expected_ms), index)
            for index in unmatched
            if abs(detected[index] - expected_ms) <= tolerance_ms
        ]
        if not candidates:
            continue
        error, selected_index = min(candidates)
        unmatched.remove(selected_index)
        errors.append(error)
    return len(errors), errors


def evaluate_scenario(
    scenario: PerturbationScenario,
    *,
    replicates: int = 20,
) -> ScenarioResult:
    truth = _truth_events()
    total_detected = 0
    total_matched = 0
    all_errors: list[int] = []
    for seed in range(replicates):
        detected, _ = detect_tap_events(_synthetic_hand_samples(scenario, seed=seed))
        matched, errors = _match_with_tolerance(truth, detected)
        total_detected += len(detected)
        total_matched += matched
        all_errors.extend(errors)

    total_truth = len(truth) * replicates
    recall = total_matched / total_truth
    precision = total_matched / total_detected if total_detected else 0.0
    count_error_rate = abs(total_detected - total_truth) / total_truth
    timing_mae_ms = mean(all_errors) if all_errors else None
    passed = (
        recall >= 0.95
        and precision >= 0.95
        and timing_mae_ms is not None
        and timing_mae_ms <= 50.0
        and count_error_rate <= 0.05
    )
    return ScenarioResult(
        name=scenario.name,
        replicates=replicates,
        truth_events=total_truth,
        detected_events=total_detected,
        matched_events=total_matched,
        recall=round(recall, 6),
        precision=round(precision, 6),
        timing_mae_ms=round(timing_mae_ms, 3) if timing_mae_ms is not None else None,
        count_error_rate=round(count_error_rate, 6),
        passed=passed,
    )


def _validate_dual_task_cost() -> dict[str, object]:
    higher = calculate_dual_task_cost(2.0, 1.6, Orientation.HIGHER_IS_BETTER)
    lower = calculate_dual_task_cost(100.0, 120.0, Orientation.LOWER_IS_BETTER)
    unstable = calculate_dual_task_cost(0.0, 1.0, Orientation.HIGHER_IS_BETTER)
    passed = (
        higher.percent_cost is not None
        and abs(higher.percent_cost - 20.0) < 1e-9
        and lower.percent_cost is not None
        and abs(lower.percent_cost - 20.0) < 1e-9
        and unstable.status is CostStatus.BASELINE_UNSTABLE
        and unstable.percent_cost is None
    )
    return {
        "passed": passed,
        "higher_is_better_percent_cost": higher.percent_cost,
        "lower_is_better_percent_cost": lower.percent_cost,
        "zero_baseline_status": unstable.status.value,
    }


def run_synthetic_validation(*, replicates: int = 20) -> dict[str, object]:
    if replicates <= 0:
        raise ValueError("replicates must be positive")
    scenario_results = [evaluate_scenario(scenario, replicates=replicates) for scenario in SCENARIOS]
    dtc_result = _validate_dual_task_cost()
    return {
        "validation_type": "synthetic engineering validation",
        "clinical_claims_supported": False,
        "scope_statement": (
            "Tests deterministic event-detection robustness and dual-task-cost arithmetic only; "
            "it does not establish performance in older adults or any disease population."
        ),
        "acceptance_thresholds": {
            "event_recall_min": 0.95,
            "event_precision_min": 0.95,
            "timing_mae_ms_max": 50.0,
            "count_error_rate_max": 0.05,
        },
        "scenarios": [asdict(result) for result in scenario_results],
        "dual_task_cost_checks": dtc_result,
        "passed": all(result.passed for result in scenario_results) and bool(dtc_result["passed"]),
    }

