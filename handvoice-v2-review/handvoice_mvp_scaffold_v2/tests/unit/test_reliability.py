import pytest

from pipelines.reliability.icc import compute_test_retest_reliability, icc_2_1

# Shrout & Fleiss (1979) 6-subject x 4-rater dataset; published ICC(2,1) = 0.290.
SHROUT_FLEISS = [
    [9, 2, 5, 8],
    [6, 1, 3, 2],
    [8, 4, 6, 8],
    [7, 1, 2, 6],
    [10, 5, 6, 9],
    [6, 2, 4, 7],
]


def test_icc_matches_published_shrout_fleiss_value():
    assert abs(icc_2_1(SHROUT_FLEISS) - 0.290) < 0.005


def test_perfect_agreement_gives_icc_one_and_zero_mdc():
    perfect = [[1.0, 1.0], [2.0, 2.0], [3.0, 3.0], [4.0, 4.0]]
    result = compute_test_retest_reliability(perfect)
    assert abs(result.icc - 1.0) < 1e-9
    assert result.band == "excellent"
    assert result.sem == 0.0
    assert result.mdc95 == 0.0


def test_mdc95_is_277_times_sem():
    result = compute_test_retest_reliability(SHROUT_FLEISS)
    assert abs(result.mdc95 - 2.77 * result.sem) < 0.02 * result.mdc95


@pytest.mark.parametrize("bad", [[[1.0, 2.0]], [[1.0], [2.0]], [[1.0, 2.0], [3.0]]])
def test_invalid_shapes_are_rejected(bad):
    with pytest.raises(ValueError):
        icc_2_1(bad)
