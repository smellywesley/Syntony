from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from statistics import median
from typing import Iterable


class Orientation(StrEnum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"


class CostStatus(StrEnum):
    OK = "ok"
    BASELINE_UNSTABLE = "baseline_unstable"
    MISSING_VALUE = "missing_value"
    NON_FINITE_VALUE = "non_finite_value"


@dataclass(frozen=True, slots=True)
class DualTaskCostResult:
    single_value: float | None
    dual_value: float | None
    absolute_difference: float | None
    percent_cost: float | None
    status: CostStatus
    orientation: Orientation
    reason: str | None = None


def calculate_dual_task_cost(
    single_value: float | None,
    dual_value: float | None,
    orientation: Orientation,
    *,
    stability_floor: float = 1e-9,
) -> DualTaskCostResult:
    """Calculate a direction-aware dual-task cost.

    Positive cost always represents deterioration. Percentage cost is omitted
    when the single-task denominator is too close to zero.
    """
    if single_value is None or dual_value is None:
        return DualTaskCostResult(single_value, dual_value, None, None, CostStatus.MISSING_VALUE, orientation, "single or dual value is missing")
    if not isfinite(single_value) or not isfinite(dual_value):
        return DualTaskCostResult(single_value, dual_value, None, None, CostStatus.NON_FINITE_VALUE, orientation, "single or dual value is non-finite")

    raw_difference = dual_value - single_value
    deterioration = -raw_difference if orientation is Orientation.HIGHER_IS_BETTER else raw_difference

    if abs(single_value) < stability_floor:
        return DualTaskCostResult(single_value, dual_value, deterioration, None, CostStatus.BASELINE_UNSTABLE, orientation, "single-task baseline is below stability floor")

    percent_cost = 100.0 * deterioration / abs(single_value)
    return DualTaskCostResult(single_value, dual_value, deterioration, percent_cost, CostStatus.OK, orientation)


def robust_condition_estimate(values: Iterable[float | None]) -> float | None:
    accepted = [float(v) for v in values if v is not None and isfinite(v)]
    return median(accepted) if accepted else None
