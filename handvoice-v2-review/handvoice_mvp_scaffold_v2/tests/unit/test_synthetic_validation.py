import pytest

from pipelines.validation.synthetic import SCENARIOS, run_synthetic_validation


def test_synthetic_engineering_validation_meets_frozen_thresholds():
    result = run_synthetic_validation(replicates=5)

    assert result["clinical_claims_supported"] is False
    assert len(result["scenarios"]) == len(SCENARIOS)
    assert result["passed"] is True


def test_synthetic_validation_rejects_nonpositive_replicates():
    with pytest.raises(ValueError, match="replicates must be positive"):
        run_synthetic_validation(replicates=0)

