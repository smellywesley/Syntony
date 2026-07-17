from pipelines.dual_task.cost import CostStatus, Orientation, calculate_dual_task_cost, robust_condition_estimate


def test_higher_is_better_positive_cost_for_deterioration():
    result = calculate_dual_task_cost(10.0, 8.0, Orientation.HIGHER_IS_BETTER)
    assert result.status is CostStatus.OK
    assert result.absolute_difference == 2.0
    assert result.percent_cost == 20.0


def test_lower_is_better_positive_cost_for_deterioration():
    result = calculate_dual_task_cost(100.0, 125.0, Orientation.LOWER_IS_BETTER)
    assert result.percent_cost == 25.0


def test_improvement_is_negative_cost():
    result = calculate_dual_task_cost(10.0, 11.0, Orientation.HIGHER_IS_BETTER)
    assert result.percent_cost == -10.0


def test_unstable_baseline_has_absolute_difference_only():
    result = calculate_dual_task_cost(0.0, 1.0, Orientation.LOWER_IS_BETTER)
    assert result.status is CostStatus.BASELINE_UNSTABLE
    assert result.percent_cost is None
    assert result.absolute_difference == 1.0


def test_condition_estimate_is_robust_median():
    assert robust_condition_estimate([1.0, 100.0, 2.0, None]) == 2.0
