"""Agreement of detected DDK syllable onsets against manual annotation.

Method anchor: DDK onset-detection validation reports one-to-one agreement
against human annotations within a millisecond tolerance window (10 ms strict,
20 ms common) using precision / recall / F1 and onset timing error
(DDKtor, Segal et al. 2022; ALS DDK validation, Rowe et al. 2022).

This scorer is the executable half of docs/HandVoice_DDK_Annotation_Protocol_v1.md.
It does NOT validate the energy detector by itself — it quantifies agreement once
manual annotations exist.
"""

from __future__ import annotations

from pipelines.common.contracts import Modality
from pipelines.validation.agreement import EventAgreement, score_event_agreement


OnsetAgreement = EventAgreement


def score_onset_agreement(
    reference_ms: list[int],
    detected_ms: list[int],
    *,
    tolerance_ms: int = 20,
) -> OnsetAgreement:
    """Score detected onsets against reference annotations within a tolerance.

    Uses the maximum-cardinality, minimum-total-lag one-to-one matcher so a
    single detected onset can validate at most one reference onset (no
    double-counting inflating recall).
    """
    return score_event_agreement(
        reference_ms,
        detected_ms,
        modality=Modality.SPEECH,
        tolerance_ms=tolerance_ms,
    )


def demo() -> None:
    """Self-check: 5 reference onsets, one detector miss + one false alarm,
    the rest within tolerance."""
    reference = [200, 400, 600, 800, 1000]
    detected = [205, 410, 590, 1300]  # 800 missed, 1300 is a false alarm
    result = score_onset_agreement(reference, detected, tolerance_ms=20)
    assert result.matched_count == 3, result.matched_count
    assert result.precision is not None and abs(result.precision - 3 / 4) < 1e-9
    assert result.recall is not None and abs(result.recall - 3 / 5) < 1e-9
    assert result.timing_mae_ms is not None and result.timing_mae_ms <= 20
    print(f"F1={result.f1:.3f} precision={result.precision:.3f} recall={result.recall:.3f} MAE={result.timing_mae_ms:.1f}ms")


if __name__ == "__main__":
    demo()
