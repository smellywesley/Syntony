# HandVoice DDK Onset Annotation & Agreement Protocol v1

## Purpose

The energy-based detector in `pipelines/audio/extractor.py` produces candidate
`/pa-ta-ka/` syllable onsets. Before any DDK rate, interval-CV, or coupling
number derived from those onsets is presented as a research feature, the
detector must be shown to agree with human annotation. This document defines
the annotation procedure and the agreement metric; `pipelines/audio/ddk_agreement.py`
is the executable scorer.

**Scope boundary:** agreement with annotation is an *engineering* validation of
the detector. It does not establish DDK construct validity, dysarthria
sensitivity, or performance in older adults — see
`HandVoice_Conference_Validation_Plan_v1.md`.

## What is annotated

`/pa-ta-ka/` is a **sequential** motion-rate (SMR) task: lips → tongue-tip →
tongue-back. The annotation records the **acoustic onset of each syllable**
(the burst/voicing onset of each /p/, /t/, /k/) across the 10 s active window.

Annotators label, per recording:

1. **Onset time (ms)** of every syllable, on the same monotonic time base the
   detector uses (0 ms = active-window start).
2. **Syllable identity** (`pa` / `ta` / `ka`) — enables later sequencing-error
   analysis; not required for onset agreement.
3. **Recording usability** (usable / unusable) with a reason (clipping, noise,
   off-task, wrong sequence).

### Annotator requirements

- Two independent annotators trained on a shared 5-recording reference set.
- Annotation in a waveform+spectrogram editor (e.g. Praat), blind to the
  detector output.
- Inter-annotator agreement is computed with the **same** scorer (one annotator
  as `reference`, the other as `detected`) and must reach the human-agreement
  target below before either annotator's marks are used as ground truth.

## Agreement metric

Detected onsets are matched to reference onsets **one-to-one** within a tolerance
window (a detected onset validates at most one reference onset — no
double-counting). Reported:

- **Precision** = matched / detected
- **Recall** = matched / reference
- **F1** = harmonic mean of precision and recall
- **Onset timing MAE (ms)** over matched pairs

**Tolerance window:** 20 ms primary, 10 ms strict — the standard reporting
windows in DDK onset-detection validation (DDKtor, Segal et al. 2022; ALS DDK
validation, Rowe et al. 2022).

### Acceptance targets (detector vs. consensus annotation)

| Metric | Target |
|---|---:|
| Onset F1 @ 20 ms | ≥ 0.90 |
| Onset timing MAE | ≤ 15 ms |
| Inter-annotator F1 @ 20 ms (gate) | ≥ 0.95 |

Targets are provisional engineering thresholds pending the clinician/SLP review
(item 5); they are not regulatory acceptance criteria.

## Corpus

Minimum 20 recordings spanning the expected acoustic range (quiet/noisy rooms,
fast/slow speakers). Report agreement per recording and pooled. A detector that
misses the F1 target is not used to produce DDK features until improved
(e.g. forced alignment / phoneme-level segmentation) or re-scoped.

## Usage

```python
from pipelines.audio.ddk_agreement import score_onset_agreement

result = score_onset_agreement(reference_onsets_ms, detected_onsets_ms, tolerance_ms=20)
print(result.f1, result.timing_mae_ms)
```
