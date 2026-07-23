from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipelines.common.contracts import Modality
from pipelines.validation.agreement import (
    evaluate_agreement_manifest,
    load_agreement_manifest,
    score_event_agreement,
    validate_agreement_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = (
    ROOT
    / "validation"
    / "examples"
    / "measurement_agreement_manifest.example.json"
)


def _case(index: int, modality: str) -> dict[str, object]:
    base = [500, 1000, 1500, 2000, 2500]
    return {
        "case_id": f"{modality}-{index:03d}",
        "modality": modality,
        "task_code": "T01" if modality == "motor" else "T02",
        "usable": True,
        "strata": {
            "device": f"reference_phone_{index % 2}",
            "condition": (
                ("clear" if index % 2 else "low_light")
                if modality == "motor"
                else ("quiet" if index % 2 else "room_noise")
            ),
            "performance_band": ("slow", "typical", "fast")[index % 3],
        },
        "rater_events_ms": {
            "rater_a": base,
            "rater_b": [value + 5 for value in base],
        },
        "consensus_events_ms": [value + 2 for value in base],
        "detected_events_ms": [value + 4 for value in base],
    }


def _manifest(*, dataset_kind: str = "human_recordings") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "profile_version": "handvoice-agreement-v1",
        "dataset_id": "agreement-corpus-v1",
        "dataset_kind": dataset_kind,
        "claim_boundary": "engineering_validation_only",
        "annotators_blinded_to_detector": True,
        "consensus_adjudicated_without_detector": True,
        "cases": [
            *[_case(index, "motor") for index in range(20)],
            *[_case(index, "speech") for index in range(20)],
        ],
    }


def test_event_agreement_is_one_to_one_and_reports_metrics():
    result = score_event_agreement(
        [200, 220],
        [210],
        modality=Modality.SPEECH,
        tolerance_ms=20,
    )
    assert result.matched_count == 1
    assert result.precision == 1.0
    assert result.recall == 0.5
    assert result.f1 == pytest.approx(2 / 3)
    assert result.timing_mae_ms == 10.0


def test_human_corpus_passes_agreement_but_never_clinical_claims():
    report = evaluate_agreement_manifest(_manifest())
    assert report["agreement_thresholds_passed"] is True
    assert report["human_recording_gate_passed"] is True
    assert report["clinical_claims_supported"] is False
    assert report["modalities"]["motor"]["passed"] is True
    assert report["modalities"]["speech"]["passed"] is True
    assert (
        report["modalities"]["speech"]["stratified_detector_agreement"][
            "performance_band=fast"
        ]["case_count"]
        == 6
    )


def test_synthetic_manifest_cannot_pass_human_recording_gate():
    report = evaluate_agreement_manifest(
        _manifest(dataset_kind="synthetic_example")
    )
    assert report["agreement_thresholds_passed"] is True
    assert report["human_recording_gate_passed"] is False
    assert report["clinical_claims_supported"] is False


def test_low_inter_rater_agreement_excludes_case_and_fails_sample_gate():
    manifest = _manifest()
    broken = manifest["cases"][0]
    broken["rater_events_ms"]["rater_b"] = [7000, 7500, 8000, 8500, 9000]
    report = evaluate_agreement_manifest(manifest)
    motor = report["modalities"]["motor"]
    assert motor["case_accounting"]["evaluable_after_inter_rater_gate"] == 19
    assert motor["minimum_sample_gate_passed"] is False
    assert motor["passed"] is False
    failed_case = next(
        case for case in report["cases"] if case["case_id"] == "motor-000"
    )
    assert failed_case["detector_evaluated"] is False
    assert failed_case["exclusion_reason"] == "inter_rater_gate_failed"


def test_manifest_enforces_blinding_and_rejects_threshold_tuning():
    manifest = _manifest()
    manifest["annotators_blinded_to_detector"] = False
    manifest["thresholds"] = {"speech_f1": 0.1}
    with pytest.raises(ValueError, match="invalid agreement manifest"):
        validate_agreement_manifest(manifest)


def test_corpus_with_one_device_fails_coverage_gate():
    manifest = _manifest()
    for case in manifest["cases"]:
        case["strata"]["device"] = "only_phone"
    report = evaluate_agreement_manifest(manifest)
    assert report["modalities"]["motor"]["coverage_gate_passed"] is False
    assert report["modalities"]["speech"]["coverage_gate_passed"] is False
    assert report["human_recording_gate_passed"] is False


def test_manifest_rejects_task_mismatch_and_duplicate_case_ids():
    manifest = _manifest()
    manifest["cases"][0]["task_code"] = "T02"
    with pytest.raises(ValueError, match="incompatible"):
        validate_agreement_manifest(manifest)

    duplicate = _manifest()
    duplicate["cases"][1]["case_id"] = duplicate["cases"][0]["case_id"]
    with pytest.raises(ValueError, match="duplicate case_id"):
        validate_agreement_manifest(duplicate)


def test_example_is_valid_but_intentionally_below_minimum_sample():
    report = evaluate_agreement_manifest(load_agreement_manifest(EXAMPLE))
    assert report["agreement_thresholds_passed"] is False
    assert report["human_recording_gate_passed"] is False
    assert all(
        not modality["minimum_sample_gate_passed"]
        for modality in report["modalities"].values()
    )


def test_json_round_trip_keeps_manifest_valid(tmp_path: Path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_manifest()), encoding="utf-8")
    loaded = load_agreement_manifest(path)
    assert loaded["dataset_id"] == "agreement-corpus-v1"


def test_duplicate_or_negative_event_times_are_rejected():
    with pytest.raises(ValueError, match="unique"):
        score_event_agreement(
            [100, 100],
            [100],
            modality="motor",
            tolerance_ms=80,
        )
    with pytest.raises(ValueError, match="non-negative"):
        score_event_agreement(
            [-1],
            [100],
            modality="motor",
            tolerance_ms=80,
        )
