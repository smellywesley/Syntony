"""Blinded human-annotation agreement gates for HandVoice event detectors.

Passing these gates supports detector measurement agreement only. It does not
establish construct validity, disease discrimination, or clinical utility.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import combinations
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

from pipelines.common.contracts import Modality, TimestampedEvent
from pipelines.coupling.events import match_events_one_to_one


SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "validation"
    / "schemas"
    / "measurement_agreement_manifest.v1.schema.json"
)


@dataclass(frozen=True, slots=True)
class AgreementThresholds:
    tolerance_ms: int
    inter_rater_f1_min: float
    inter_rater_case_pass_rate_min: float
    detector_precision_min: float
    detector_recall_min: float
    detector_f1_min: float
    detector_timing_mae_ms_max: float
    minimum_evaluable_cases: int
    minimum_device_strata: int
    minimum_condition_strata: int
    minimum_performance_band_strata: int
    minimum_cases_per_required_stratum: int


FROZEN_THRESHOLDS: dict[Modality, AgreementThresholds] = {
    Modality.MOTOR: AgreementThresholds(
        tolerance_ms=80,
        inter_rater_f1_min=0.90,
        inter_rater_case_pass_rate_min=0.95,
        detector_precision_min=0.90,
        detector_recall_min=0.90,
        detector_f1_min=0.90,
        detector_timing_mae_ms_max=50.0,
        minimum_evaluable_cases=20,
        minimum_device_strata=2,
        minimum_condition_strata=2,
        minimum_performance_band_strata=3,
        minimum_cases_per_required_stratum=3,
    ),
    Modality.SPEECH: AgreementThresholds(
        tolerance_ms=20,
        inter_rater_f1_min=0.95,
        inter_rater_case_pass_rate_min=0.95,
        detector_precision_min=0.90,
        detector_recall_min=0.90,
        detector_f1_min=0.90,
        detector_timing_mae_ms_max=15.0,
        minimum_evaluable_cases=20,
        minimum_device_strata=2,
        minimum_condition_strata=2,
        minimum_performance_band_strata=3,
        minimum_cases_per_required_stratum=3,
    ),
}


@dataclass(frozen=True, slots=True)
class EventAgreement:
    reference_count: int
    detected_count: int
    matched_count: int
    precision: float | None
    recall: float | None
    f1: float | None
    timing_mae_ms: float | None
    total_abs_timing_error_ms: int
    tolerance_ms: int


def _validated_times(values: Sequence[int], *, label: str) -> list[int]:
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise ValueError(f"{label} must contain integer millisecond timestamps")
    if any(value < 0 for value in values):
        raise ValueError(f"{label} timestamps must be non-negative")
    if len(set(values)) != len(values):
        raise ValueError(f"{label} timestamps must be unique")
    return sorted(values)


def _as_events(
    times_ms: Sequence[int],
    *,
    prefix: str,
    modality: Modality,
) -> list[TimestampedEvent]:
    event_type = "tap_opening" if modality is Modality.MOTOR else "ddk_syllable_onset"
    return [
        TimestampedEvent(
            event_id=f"{prefix}-{index}",
            modality=modality,
            event_type=event_type,
            start_ms=timestamp,
        )
        for index, timestamp in enumerate(times_ms)
    ]


def _metrics(
    *,
    reference_count: int,
    detected_count: int,
    matched_count: int,
    total_abs_timing_error_ms: int,
    tolerance_ms: int,
) -> EventAgreement:
    precision = matched_count / detected_count if detected_count else None
    recall = matched_count / reference_count if reference_count else None
    if reference_count == 0 and detected_count == 0:
        f1 = None
    elif precision is None or recall is None or precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)
    timing_mae_ms = (
        total_abs_timing_error_ms / matched_count if matched_count else None
    )
    return EventAgreement(
        reference_count=reference_count,
        detected_count=detected_count,
        matched_count=matched_count,
        precision=precision,
        recall=recall,
        f1=f1,
        timing_mae_ms=timing_mae_ms,
        total_abs_timing_error_ms=total_abs_timing_error_ms,
        tolerance_ms=tolerance_ms,
    )


def score_event_agreement(
    reference_ms: Sequence[int],
    detected_ms: Sequence[int],
    *,
    modality: Modality | str,
    tolerance_ms: int,
) -> EventAgreement:
    """Score maximum-cardinality, minimum-lag one-to-one event agreement."""
    if tolerance_ms < 0:
        raise ValueError("tolerance_ms must be non-negative")
    resolved_modality = Modality(modality)
    if resolved_modality not in FROZEN_THRESHOLDS:
        raise ValueError("agreement scoring supports motor and speech modalities only")
    reference_times = _validated_times(reference_ms, label="reference_ms")
    detected_times = _validated_times(detected_ms, label="detected_ms")
    reference = _as_events(reference_times, prefix="ref", modality=resolved_modality)
    detected = _as_events(detected_times, prefix="det", modality=resolved_modality)
    matches = match_events_one_to_one(reference, detected, window_ms=tolerance_ms)
    return _metrics(
        reference_count=len(reference),
        detected_count=len(detected),
        matched_count=len(matches),
        total_abs_timing_error_ms=sum(abs(match.lag_ms) for match in matches),
        tolerance_ms=tolerance_ms,
    )


def _pooled_score(
    scores: Sequence[EventAgreement],
    *,
    tolerance_ms: int,
) -> EventAgreement:
    return _metrics(
        reference_count=sum(score.reference_count for score in scores),
        detected_count=sum(score.detected_count for score in scores),
        matched_count=sum(score.matched_count for score in scores),
        total_abs_timing_error_ms=sum(
            score.total_abs_timing_error_ms for score in scores
        ),
        tolerance_ms=tolerance_ms,
    )


def _score_dict(score: EventAgreement) -> dict[str, Any]:
    result = asdict(score)
    result.pop("total_abs_timing_error_ms")
    return result


def _passes_detector_gate(
    score: EventAgreement,
    thresholds: AgreementThresholds,
) -> bool:
    return bool(
        score.precision is not None
        and score.precision >= thresholds.detector_precision_min
        and score.recall is not None
        and score.recall >= thresholds.detector_recall_min
        and score.f1 is not None
        and score.f1 >= thresholds.detector_f1_min
        and score.timing_mae_ms is not None
        and score.timing_mae_ms <= thresholds.detector_timing_mae_ms_max
    )


def _validate_task_modality(case: Mapping[str, Any]) -> None:
    modality = Modality(case["modality"])
    allowed_tasks = {
        Modality.MOTOR: {"T01", "T03"},
        Modality.SPEECH: {"T02", "T03"},
    }
    if case["task_code"] not in allowed_tasks[modality]:
        raise ValueError(
            f"case {case['case_id']} task {case['task_code']} is incompatible "
            f"with modality {modality.value}"
        )


def validate_agreement_manifest(manifest: Mapping[str, Any]) -> None:
    """Validate the frozen v1 contract and cross-field invariants."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(manifest),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        details = "; ".join(
            f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
            f"{error.message}"
            for error in errors
        )
        raise ValueError(f"invalid agreement manifest: {details}")

    case_ids: set[str] = set()
    for case in manifest["cases"]:
        if case["case_id"] in case_ids:
            raise ValueError(f"duplicate case_id: {case['case_id']}")
        case_ids.add(case["case_id"])
        _validate_task_modality(case)


def load_agreement_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("agreement manifest must be a JSON object")
    validate_agreement_manifest(manifest)
    return manifest


def _evaluate_usable_case(
    case: Mapping[str, Any],
    *,
    modality: Modality,
    thresholds: AgreementThresholds,
) -> tuple[dict[str, Any], EventAgreement | None]:
    rater_events = case["rater_events_ms"]
    rater_pairs: list[dict[str, Any]] = []
    inter_rater_scores: list[EventAgreement] = []
    for first_id, second_id in combinations(sorted(rater_events), 2):
        score = score_event_agreement(
            rater_events[first_id],
            rater_events[second_id],
            modality=modality,
            tolerance_ms=thresholds.tolerance_ms,
        )
        inter_rater_scores.append(score)
        rater_pairs.append(
            {"raters": [first_id, second_id], "agreement": _score_dict(score)}
        )

    consensus_scores: list[EventAgreement] = []
    consensus_checks: list[dict[str, Any]] = []
    for rater_id in sorted(rater_events):
        score = score_event_agreement(
            case["consensus_events_ms"],
            rater_events[rater_id],
            modality=modality,
            tolerance_ms=thresholds.tolerance_ms,
        )
        consensus_scores.append(score)
        consensus_checks.append(
            {"rater": rater_id, "agreement": _score_dict(score)}
        )
    reliability_scores = [*inter_rater_scores, *consensus_scores]
    inter_rater_passed = bool(reliability_scores) and all(
        score.f1 is not None and score.f1 >= thresholds.inter_rater_f1_min
        for score in reliability_scores
    )
    minimum_f1 = min(
        (score.f1 for score in reliability_scores if score.f1 is not None),
        default=None,
    )
    result: dict[str, Any] = {
        "case_id": case["case_id"],
        "modality": modality.value,
        "task_code": case["task_code"],
        "usable": True,
        "strata": dict(case["strata"]),
        "inter_rater": {
            "minimum_f1": minimum_f1,
            "target": thresholds.inter_rater_f1_min,
            "passed": inter_rater_passed,
            "pairs": rater_pairs,
            "consensus_checks": consensus_checks,
        },
    }
    if not inter_rater_passed:
        result["detector_evaluated"] = False
        result["exclusion_reason"] = "inter_rater_gate_failed"
        return result, None

    detector_score = score_event_agreement(
        case["consensus_events_ms"],
        case["detected_events_ms"],
        modality=modality,
        tolerance_ms=thresholds.tolerance_ms,
    )
    result["detector_evaluated"] = True
    result["detector_agreement"] = _score_dict(detector_score)
    return result, detector_score


def _stratified_scores(
    eligible: Sequence[tuple[Mapping[str, Any], EventAgreement]],
    *,
    tolerance_ms: int,
) -> dict[str, Any]:
    groups: dict[str, list[EventAgreement]] = {}
    for case, score in eligible:
        for name, value in sorted(case["strata"].items()):
            groups.setdefault(f"{name}={value}", []).append(score)
    return {
        group: {
            "case_count": len(scores),
            "detector_agreement": _score_dict(
                _pooled_score(scores, tolerance_ms=tolerance_ms)
            ),
        }
        for group, scores in sorted(groups.items())
    }


def _coverage_gate(
    eligible: Sequence[tuple[Mapping[str, Any], EventAgreement]],
    thresholds: AgreementThresholds,
) -> tuple[bool, dict[str, Any]]:
    required_counts = {
        "device": thresholds.minimum_device_strata,
        "condition": thresholds.minimum_condition_strata,
        "performance_band": thresholds.minimum_performance_band_strata,
    }
    details: dict[str, Any] = {}
    passed = True
    for field, required_distinct in required_counts.items():
        counts: dict[str, int] = {}
        for case, _ in eligible:
            value = case["strata"].get(field)
            if value is not None:
                counts[value] = counts.get(value, 0) + 1
        field_passed = (
            len(counts) >= required_distinct
            and bool(counts)
            and min(counts.values()) >= thresholds.minimum_cases_per_required_stratum
        )
        passed = passed and field_passed
        details[field] = {
            "counts": dict(sorted(counts.items())),
            "minimum_distinct_values": required_distinct,
            "minimum_cases_per_value": thresholds.minimum_cases_per_required_stratum,
            "passed": field_passed,
        }
    return passed, details


def evaluate_agreement_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate a manifest against immutable v1 release gates."""
    validate_agreement_manifest(manifest)
    case_results: list[dict[str, Any]] = []
    modality_results: dict[str, Any] = {}

    for modality, thresholds in FROZEN_THRESHOLDS.items():
        modality_cases = [
            case for case in manifest["cases"] if case["modality"] == modality.value
        ]
        usable_cases = [case for case in modality_cases if case["usable"]]
        unusable_cases = [case for case in modality_cases if not case["usable"]]
        eligible: list[tuple[Mapping[str, Any], EventAgreement]] = []

        for case in modality_cases:
            if not case["usable"]:
                case_results.append(
                    {
                        "case_id": case["case_id"],
                        "modality": modality.value,
                        "task_code": case["task_code"],
                        "usable": False,
                        "detector_evaluated": False,
                        "exclusion_reason": case["exclusion_reason"],
                        "strata": dict(case["strata"]),
                    }
                )
                continue
            result, detector_score = _evaluate_usable_case(
                case,
                modality=modality,
                thresholds=thresholds,
            )
            case_results.append(result)
            if detector_score is not None:
                eligible.append((case, detector_score))

        pass_rate = len(eligible) / len(usable_cases) if usable_cases else 0.0
        pooled = _pooled_score(
            [score for _, score in eligible],
            tolerance_ms=thresholds.tolerance_ms,
        )
        sample_gate_passed = len(eligible) >= thresholds.minimum_evaluable_cases
        inter_rater_gate_passed = (
            bool(usable_cases)
            and pass_rate >= thresholds.inter_rater_case_pass_rate_min
        )
        detector_gate_passed = _passes_detector_gate(pooled, thresholds)
        coverage_gate_passed, coverage = _coverage_gate(eligible, thresholds)
        modality_results[modality.value] = {
            "thresholds": asdict(thresholds),
            "case_accounting": {
                "total": len(modality_cases),
                "usable": len(usable_cases),
                "unusable": len(unusable_cases),
                "evaluable_after_inter_rater_gate": len(eligible),
            },
            "inter_rater_case_pass_rate": pass_rate,
            "inter_rater_gate_passed": inter_rater_gate_passed,
            "minimum_sample_gate_passed": sample_gate_passed,
            "coverage_gate_passed": coverage_gate_passed,
            "coverage": coverage,
            "detector_agreement": _score_dict(pooled),
            "detector_gate_passed": detector_gate_passed,
            "stratified_detector_agreement": _stratified_scores(
                eligible,
                tolerance_ms=thresholds.tolerance_ms,
            ),
            "passed": (
                inter_rater_gate_passed
                and sample_gate_passed
                and coverage_gate_passed
                and detector_gate_passed
            ),
        }

    thresholds_passed = all(
        result["passed"] for result in modality_results.values()
    )
    human_recording_gate_passed = (
        manifest["dataset_kind"] == "human_recordings" and thresholds_passed
    )
    return {
        "validation_type": "blinded human-annotation detector agreement",
        "profile_version": manifest["profile_version"],
        "dataset_id": manifest["dataset_id"],
        "dataset_kind": manifest["dataset_kind"],
        "clinical_claims_supported": False,
        "scope_statement": (
            "A passing result supports event-detector agreement with blinded "
            "annotations only. It does not establish clinical validity, diagnostic "
            "accuracy, disease sensitivity, or clinical utility."
        ),
        "agreement_thresholds_passed": thresholds_passed,
        "human_recording_gate_passed": human_recording_gate_passed,
        "modalities": modality_results,
        "cases": sorted(case_results, key=lambda result: result["case_id"]),
    }
