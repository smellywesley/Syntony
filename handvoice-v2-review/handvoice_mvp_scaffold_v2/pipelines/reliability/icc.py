"""Test-retest reliability: ICC(2,1), SEM, and MDC95.

Method anchor: Koo & Li (2016), "A Guideline of Selecting and Reporting
Intraclass Correlation Coefficients for Reliability Research", J Chiropr Med.
For test-retest reliability the appropriate form is a two-way random-effects,
single-measure, *absolute-agreement* ICC (ICC(2,1)): sessions are a random
sample and systematic session-to-session shifts must count as error, which the
absolute-agreement (not consistency) definition captures.

    SEM   = SD * sqrt(1 - ICC)          (within-subject standard error)
    MDC95 = 1.96 * sqrt(2) * SEM        (~2.77 * SEM; change beyond measurement error)

Reliability bands (Koo & Li): <0.5 poor, 0.5-0.75 moderate,
0.75-0.9 good, >0.9 excellent.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import pstdev


@dataclass(frozen=True, slots=True)
class ReliabilityResult:
    icc: float
    sem: float
    mdc95: float
    band: str
    subjects: int
    sessions: int


def _reliability_band(icc: float) -> str:
    if icc < 0.5:
        return "poor"
    if icc < 0.75:
        return "moderate"
    if icc < 0.9:
        return "good"
    return "excellent"


def icc_2_1(ratings: list[list[float]]) -> float:
    """ICC(2,1): two-way random effects, single measure, absolute agreement.

    ``ratings`` is a subjects x sessions matrix (one row per subject, one
    column per repeated session). Every row must have the same length. Requires
    at least 2 subjects and 2 sessions.
    """
    n = len(ratings)
    if n < 2:
        raise ValueError("ICC requires at least 2 subjects")
    k = len(ratings[0])
    if k < 2:
        raise ValueError("ICC requires at least 2 sessions")
    if any(len(row) != k for row in ratings):
        raise ValueError("every subject must have the same number of sessions")

    grand = sum(sum(row) for row in ratings) / (n * k)
    row_means = [sum(row) / k for row in ratings]
    col_means = [sum(ratings[i][j] for i in range(n)) / n for j in range(k)]

    ss_rows = k * sum((rm - grand) ** 2 for rm in row_means)
    ss_cols = n * sum((cm - grand) ** 2 for cm in col_means)
    ss_total = sum((ratings[i][j] - grand) ** 2 for i in range(n) for j in range(k))
    ss_error = ss_total - ss_rows - ss_cols

    ms_rows = ss_rows / (n - 1)
    ms_cols = ss_cols / (k - 1)
    ms_error = ss_error / ((n - 1) * (k - 1))

    denominator = ms_rows + (k - 1) * ms_error + (k / n) * (ms_cols - ms_error)
    if denominator == 0:
        return 0.0
    return (ms_rows - ms_error) / denominator


def compute_test_retest_reliability(ratings: list[list[float]]) -> ReliabilityResult:
    """Full reliability summary: ICC(2,1) with SEM and MDC95 in raw units.

    SEM uses the pooled standard deviation across all observations, so SEM and
    MDC95 are expressed in the feature's own units (e.g. Hz, proportion).
    """
    icc = icc_2_1(ratings)
    pooled_sd = pstdev([value for row in ratings for value in row])
    # Negative ICC (error exceeds between-subject variance) floors to 0 for SEM.
    sem = pooled_sd * sqrt(max(0.0, 1.0 - icc))
    mdc95 = 1.96 * sqrt(2) * sem
    return ReliabilityResult(
        icc=icc,
        sem=sem,
        mdc95=mdc95,
        band=_reliability_band(icc),
        subjects=len(ratings),
        sessions=len(ratings[0]),
    )


def demo() -> None:
    """Self-check against Shrout & Fleiss (1979) 6-subject x 4-rater data,
    whose published ICC(2,1) is 0.290."""
    ratings = [
        [9, 2, 5, 8],
        [6, 1, 3, 2],
        [8, 4, 6, 8],
        [7, 1, 2, 6],
        [10, 5, 6, 9],
        [6, 2, 4, 7],
    ]
    icc = icc_2_1(ratings)
    assert abs(icc - 0.290) < 0.005, icc
    result = compute_test_retest_reliability(ratings)
    assert result.band == "poor", result.band
    assert result.mdc95 > result.sem > 0
    print(f"ICC(2,1)={result.icc:.3f} SEM={result.sem:.3f} MDC95={result.mdc95:.3f} band={result.band}")


if __name__ == "__main__":
    demo()
