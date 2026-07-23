# HandVoice Measurement Agreement Protocol v1

## Decision this protocol supports

This protocol answers one narrow question: do HandVoice motor- and
speech-event timestamps agree with blinded human annotations closely enough to
use those events as engineering measurements in a feasibility study?

A pass does **not** establish Parkinson's detection, diagnostic accuracy,
clinical construct validity, sensitivity to change, or clinical utility.

## Locked workflow

1. Assign each recording a pseudonymous case ID. Do not place names, medical
   record numbers, dates of birth, media paths, or contact details in the
   manifest.
2. Two or more trained annotators independently mark event times on the
   0-10,000 ms active-window timebase while blinded to HandVoice output.
3. Annotators adjudicate a consensus without seeing detector output.
4. Export rater, consensus, and detector timestamps into the v1 JSON manifest.
   The schema rejects non-blinded workflows and post-hoc threshold fields.
5. Run the scorer once on the frozen corpus. Preserve the manifest hash,
   software commit, dirty-tree state, and complete machine-readable report.
   The CLI records these fields automatically; a dirty tree is not an
   acceptable release artifact.

Manual motor annotation marks maximal tap opening. Manual speech annotation
marks the acoustic onset of each `/pa-ta-ka/` syllable. A detector event can
match at most one reference event.

## Frozen engineering gates

| Gate | Motor | Speech |
|---|---:|---:|
| One-to-one tolerance | 80 ms | 20 ms |
| Per-case inter-rater F1 | >= 0.90 | >= 0.95 |
| Cases passing inter-rater gate | >= 95% | >= 95% |
| Evaluable recordings | >= 20 | >= 20 |
| Detector precision | >= 0.90 | >= 0.90 |
| Detector recall | >= 0.90 | >= 0.90 |
| Detector F1 | >= 0.90 | >= 0.90 |
| Detector timing MAE | <= 50 ms | <= 15 ms |
| Device strata | >= 2, >= 3 cases each | >= 2, >= 3 cases each |
| Capture-condition strata | >= 2, >= 3 cases each | >= 2, >= 3 cases each |
| Performance bands | >= 3, >= 3 cases each | >= 3, >= 3 cases each |

These are provisional engineering release gates, not regulatory limits. They
must be reviewed by the relevant clinician, speech-language professional, and
statistician before a human study. Changing a threshold requires a new profile
version and written rationale; it must not be tuned after seeing results.

## Corpus construction and stress conditions

Each modality needs at least 20 evaluable recordings after the inter-rater
gate. Include deliberately varied strata:

- at least two supported device classes;
- clear/quiet and degraded conditions (low light or partial occlusion for
  motor; ordinary room noise for speech);
- slow, typical, and fast performance bands; and
- the intended camera distance and positioning range.

The report pools event counts rather than averaging per-recording percentages,
and separately reports every supplied `strata` value. A strong pooled score
with a weak device or condition stratum is not evidence of robustness.

## Run

Copy the synthetic example structure, replace it with approved pseudonymous
annotations, and retain the example's fixed metadata fields:

```powershell
python scripts/score_measurement_agreement.py `
  validation/manifests/measurement_agreement.v1.json `
  --output validation/results/measurement_agreement.json
```

Exit status:

- `0`: both modality gates passed on a manifest marked `human_recordings`;
- `1`: valid analysis, but a reliability, sample, detector, or human-recording
  gate failed;
- `2`: invalid or unreadable manifest.

The included synthetic example intentionally returns `1`: it demonstrates the
contract but has neither human recordings nor the minimum sample.

## What must happen after this passes

Agreement is only the first human-evidence rung. Next are protocol-approved
healthy-volunteer usability, test-retest reliability with confidence
intervals, older-adult feasibility, comparison with clinician-defined
reference measures, and only then a powered clinical-discrimination study.
