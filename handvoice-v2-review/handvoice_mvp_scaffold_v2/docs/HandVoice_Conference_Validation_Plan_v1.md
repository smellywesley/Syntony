# HandVoice Conference Validation Plan v1

## Honest scientific position

HandVoice is an engineering-validation prototype for synchronized motor-speech measurement. It is not a Parkinson's detector, a diagnostic device, or a clinically validated assessment of older adults. No human-participant evidence or ethics approval is currently available, so no clinical accuracy, age-group generalization, disease discrimination, or health-outcome claim is permitted.

## Research contribution that can be defended now

The defensible contribution is a reproducible measurement architecture that:

1. freezes a synchronized 15-second capture protocol with a 10-second active window;
2. derives hand-opening events and speech timing on the same monotonic time base;
3. calculates direction-aware dual-task costs without unstable-denominator fabrication;
4. exposes exploratory, one-to-one motor-speech event coupling; and
5. rejects malformed, unsynchronized, cross-task, or path-unsafe inputs before analysis.

## Engineering validation question

Does the deterministic tap-event and dual-task-cost pipeline preserve known synthetic ground truth under plausible sampling-rate, timestamp-jitter, noise, frame-dropout, duplicate-frame, and submission-order perturbations?

## Frozen synthetic experiment

- Signal: 19 known tap openings over a 10-second active window.
- Sampling: 15 or 30 frames per second.
- Perturbations: up to 10 ms timestamp jitter, Gaussian signal noise, 10% frame dropout, duplicate timestamps, and reversed frame submission order.
- Replicates: 20 deterministic random seeds per condition.
- Matching tolerance: 80 ms, one detected event to at most one ground-truth event.

### Acceptance thresholds

| Metric | Threshold |
|---|---:|
| Event recall | >= 0.95 |
| Event precision | >= 0.95 |
| Event timing mean absolute error | <= 50 ms |
| Absolute event-count error rate | <= 0.05 |
| Direction-aware DTC arithmetic cases | 100% pass |

Run the frozen experiment with:

```powershell
python scripts/run_synthetic_validation.py
```

The machine-readable result is written to `validation/results/synthetic_validation.json`. A failed threshold returns a non-zero process exit code.

## What this experiment cannot establish

Synthetic success does not demonstrate usability by older adults, robustness to real occlusion or dysarthric speech, clinical construct validity, test-retest reliability, medication sensitivity, disease specificity, or diagnostic performance. Those require approved human-participant work and appropriate clinical comparators.

## Next ethical evidence ladder

1. Bench validation with prerecorded or purpose-built non-human synthetic media.
2. Usability study with healthy adult volunteers under an approved protocol.
3. Older-adult feasibility study measuring completion, missingness, and repeatability—not diagnosis.
4. Only after feasibility: powered clinical comparison with clinician-defined reference measures and preregistered endpoints.

Until steps 2-4 exist, presentations must use the phrase **engineering-validation prototype** and show synthetic results as software evidence, not biomedical efficacy.

