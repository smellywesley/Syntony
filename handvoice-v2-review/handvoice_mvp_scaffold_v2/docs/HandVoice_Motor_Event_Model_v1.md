# HandVoice Motor Event Model v1

## Decision

HandVoice may use a trained motor-event model only as a temporal interpretation
layer on top of computer-vision hand tracking:

```text
camera video
  -> local MediaPipe hand detection and 21-landmark tracking
  -> normalized landmark geometry and tracking-quality signals
  -> temporal motor-event model
  -> tap timestamps, confidence, amplitude and rhythm features
```

The model does not process identity, diagnose Parkinson's disease, output
MDS-UPDRS, recommend treatment or override the existing quality gate.

## Why this architecture

HUBU-FIS contains 234 finger-tapping videos. That is useful for a compact
temporal model but too small for a defensible end-to-end video network trained
from pixels. MediaPipe supplies pretrained visual perception. The HandVoice
model learns only the narrower relationship between tracked landmark dynamics
and blinded human-marked tap openings.

The v1 model is regularized logistic classification over local temporal
features:

- normalized thumb-index distance;
- thumb-index angle;
- incoming and outgoing velocity;
- local peak prominence;
- MediaPipe tracking confidence;
- local valid-frame fraction; and
- neighboring frame-gap size.

This deliberately simple baseline is auditable, small enough for local use and
appropriate for the first human-labelled corpus. A temporal convolutional
network is not justified until this baseline has been evaluated and a larger
corpus exists.

## Tracking and failure behaviour

The trained model supplements computer vision; it does not replace it.

- Invalid MediaPipe frames are never model candidates.
- Frames below 0.5 tracking confidence are rejected again by the backend even
  if a client incorrectly labels them valid.
- A candidate is suppressed when fewer than 80% of its local frames are valid.
- Existing recording-level hand visibility, frame-rate, guide-position and
  wrong-hand checks still run after inference.
- Model confidence is stored on each event.
- Model version, artifact SHA-256, dataset ID and release-gate status are stored
  with derived motor events and features.
- If the model setting is disabled, HandVoice uses the existing deterministic
  peak detector.
- If the model setting is enabled but its artifact is missing, malformed,
  unvalidated or unapproved, the API refuses to start. It never silently
  substitutes a model during a real capture.

## Supported task boundary

The trained v1 artifact is eligible for `T01` only. HUBU-FIS does not contain
the simultaneous hand-speech `T03` protocol, so T03 continues to use the
deterministic detector. A future T03 model requires separately consented
dual-task recordings and its own held-out evaluation.

## Dataset and annotation preparation

Raw media and development artifacts must remain outside Git:

```text
data/external/hubu-fis/       # ignored
models/development/           # ignored
validation/manifests/         # ignored private case-level study manifests
```

For each selected right-hand video:

1. Assign a pseudonymous case ID and participant ID.
2. Preserve the source-video SHA-256 in the private manifest.
3. Open `/capture/research-extractor.html` on the local HandVoice server,
   select the approved video and its ten-second active window, and export the
   same MediaPipe 21-landmark output used by live HandVoice.
4. Have at least two trained raters independently open
   `/capture/motor-annotator.html` and mark maximal tap opening.
5. Keep raters blinded to deterministic and ML detector output.
6. Adjudicate consensus without showing detector output.
7. Split by participant before training. Both hands or repeated videos from one
   person must never cross train, validation and test partitions.

The schema is:

```text
validation/schemas/motor_training_manifest.v1.schema.json
```

The illustrative manifest contains fake hashes and cannot be trained directly:

```text
validation/examples/motor_training_manifest.example.json
```

Landmark files use this contract. The point array below is abbreviated for
readability and is not itself valid training input:

```json
{
  "schema_version": "1.0",
  "case_id": "motor-001",
  "frames": [
    {
      "timestamp_ms": 0,
      "handedness": "right",
      "landmarks_xyz": [[0.0, 0.0, 0.0]],
      "median_confidence": 0.96,
      "validity": "valid"
    }
  ]
}
```

`landmarks_xyz` must contain exactly 21 three-dimensional points per frame.
The loader rejects traversal outside the configured data root, SHA-256
mismatches, duplicate timestamps, non-finite coordinates, left-hand cases and
failed inter-rater agreement.

The research extractor runs entirely in the browser. It neither uploads the
video nor stores it in the HandVoice database. It displays the source-video
SHA-256 so the private manifest can bind the landmark track to the approved
source. Tracking must be reviewed before annotation; an exported file is not
automatically an evaluable case.

The annotation screen is intentionally separate and shows no landmarks,
diagnosis, UPDRS or detector output. Each rater exports an independent event
file. Consensus adjudication and assembly of the training manifest happen only
after both files are locked.

## Assemble the training manifest

Create a private study plan using
`validation/schemas/motor_study_plan.v1.schema.json`. Each case references its
source video, exported landmark file, at least two independent rater exports,
the adjudicated consensus events and its assigned participant-level split.

Then assemble the trainer input:

```powershell
python scripts/assemble_motor_training_manifest.py `
  data/external/hubu-fis/study-plan.json `
  --data-root data/external/hubu-fis `
  --output validation/manifests/motor_training.v1.json
```

The assembler validates the study-plan and annotation schemas, rejects path
escape, mismatched case/rater identities and participant leakage, and computes
the landmark and source-video SHA-256 values itself. This prevents manual hash
copying and binds the final manifest to the exact CV track and source recording.

## Train

After approved landmark files and annotations exist:

```powershell
python scripts/train_motor_event_model.py `
  validation/manifests/motor_training.v1.json `
  --data-root data/external/hubu-fis `
  --model-version motor-event-v1 `
  --artifact models/development/motor-event-v1.json `
  --report validation/results/motor_model_training_v1.json
```

The trainer:

1. verifies hashes and annotation contracts;
2. verifies that participants do not cross partitions;
3. fits scaling parameters on the training partition only;
4. fits the temporal logistic model;
5. selects the event-probability threshold on validation participants only;
6. evaluates the untouched test participants once; and
7. writes a data-only JSON artifact, never an executable pickle.

Exit code `0` means the frozen release gate passed, `1` means training completed
but the artifact is not release-eligible, and `2` means the inputs were
invalid.

## Frozen model-release gate

The API accepts an enabled artifact only when all of the following are true:

- human recordings and human annotations;
- annotators blinded to detector output;
- participant-grouped train/validation/test partitions;
- a recorded software revision and clean training working tree;
- at least 20 untouched test recordings;
- at least two device strata, two capture-condition strata and three
  performance-band strata, with at least three test cases in every represented
  required stratum;
- precision, recall and F1 each at least 0.90; and
- timing MAE no greater than 50 ms.

These are provisional engineering agreement gates, not diagnostic or
regulatory thresholds.

## Enable only after the gate passes

Promote the reviewed artifact to a controlled release path and configure:

```text
HANDVOICE_MOTOR_EVENT_MODEL_ENABLED=true
HANDVOICE_MOTOR_EVENT_MODEL_PATH=models/releases/motor-event-v1.json
```

Until a human-trained artifact passes, both settings remain unset and the demo
continues using deterministic motor-event measurement.

## Current status

Implemented:

- CV-quality-aware temporal features;
- model training and threshold selection;
- participant leakage protection;
- inter-rater and consensus checks;
- hash-verified blinded-annotation manifest assembly;
- safe JSON artifact loading;
- model confidence and provenance persistence;
- disabled-by-default T01 integration;
- deterministic fallback; and
- startup rejection of missing or non-release artifacts.

Not yet completed:

- acquisition and pseudonymisation of the selected HUBU-FIS subset;
- blinded annotation of human recordings;
- actual human-data model training;
- two-device/two-condition external evaluation; and
- clinician/statistician approval of the release thresholds.

Therefore, no trained artifact is currently claimed as clinically valid.
