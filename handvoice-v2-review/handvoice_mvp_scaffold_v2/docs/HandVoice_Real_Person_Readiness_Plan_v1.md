# HandVoice Real-Person Readiness Plan v1

Date: 22 July 2026

## Verdict

HandVoice is ready for controlled local demonstrations with synthetic or
prerecorded media. It is not approved for patient recording. The next permitted
human step is a consented, non-clinical engineering study with healthy adult
volunteers after a named data owner approves consent, retention, deletion and
incident procedures.

## What computer vision does today

The browser runs MediaPipe Hand Landmarker locally. Its pipeline uses a palm
detector to locate a region of interest, followed by a landmark model that
estimates 21 hand points. On video, tracking reuses the prior region until
confidence drops, reducing the need to run full detection on every frame.

```text
camera frame + monotonic timestamp
        |
        v
MediaPipe palm detector -> hand ROI -> 21-landmark model -> temporal tracking
        |                                           |
        |                                           v
        |                               handedness + confidence
        v                                           |
right-hand/guide QC <--------------------------------+
        |
        v
timestamped landmark frames -> deterministic tap events
        |                              |
        +------ synchronized ----------+---- audio waveform -> speech candidates
                                       |
                                       v
                         quality decision + aligned report
```

The yellow/orange guide is a static placement zone, not a detection result.
Actual detections are the teal landmark points drawn during capture.

## Why “track everything” is not a validation strategy

MediaPipe Holistic can output 543 landmarks: 33 pose, 468 face and 21 for each
hand. More landmarks do not create a valid clinical measure. Face landmarks,
blendshapes, head pose, blinks and gaze are different constructs with different
ground truth, sampling requirements, error modes and privacy implications.

Do not add a signal until all five fields are defined:

1. Construct: exactly what physical behavior is being measured.
2. Action: what a qualified reviewer will do differently because of it.
3. Reference: the human-rated or instrumented ground truth.
4. Metric: error measure and pass threshold fixed before data collection.
5. Claim boundary: what the output explicitly cannot establish.

Face/head/eye tracking therefore remains a separate research module. MediaPipe
Face Landmarker can provide facial landmarks, blendshapes and a facial
transformation matrix; it does not by itself validate emotion, cognition,
neurological status, attention or precise eye gaze.

## Critique of the current workflow

### Keep

- One coded participant, one fixed T01 -> T02 -> T03 session.
- Explicit privacy/stop acknowledgement before device access.
- Live right-hand presence and placement feedback.
- At most two attempts per task.
- Atomic accept/retry/review decisions and synchronized reporting.

### Fix before consented volunteer recording

| Priority | Gap | Required exit evidence |
|---|---|---|
| P0 | No approved human-data protocol | Named approver signs consent, data inventory, retention, deletion and incident plan |
| P0 | No reliable deletion workflow | Operator can delete a session and its media; test proves DB rows and files are removed |
| P0 | Local demo auth bypass | Demonstrate it binds only to loopback and is false by default; never use it for patient data |
| P1 | Hand guide can be mistaken for detection | Labeled rectangular zone and separate landmark overlay verified with five users |
| P1 | No device-performance evidence | Five complete runs on each of three phones with FPS, rejection rate and report latency |
| P1 | No golden QC media set | 30 consented/licensed clips, independently labeled, with 100% expected decision matching |
| P1 | Speech segmentation remains exploratory | Reference annotations and preregistered F1/timing thresholds |
| P2 | No CI, backup or rollback procedure | Clean-checkout build/test job plus tested backup/restore and rollback instructions |

## Validation ladder

### Gate 0 — software repeatability

- Unit, integration and browser E2E suites pass from a clean checkout.
- Five consecutive browser journeys pass.
- Media concurrency test passes 50/50.
- All failure paths delete or quarantine media without creating accepted output.

### Gate 1 — bench media

- Use synthetic/licensed prerecorded media only.
- Golden QC set: at least 30 clips spanning every rejection code.
- Expected quality-decision match: 100% for the frozen set.
- Measure p50/p95 recording-to-report latency and peak browser memory.

### Gate 2 — consented healthy-adult engineering study

- Not patients and no diagnosis/health history collected.
- Ethics/privacy owner approves the written protocol first.
- Use coded IDs; collect the minimum necessary video/audio.
- Record device model, browser version, lighting and distance.
- Report completion, retry, stop, missing-frame and latency distributions.

### Gate 3 — measurement agreement

- Two blinded annotators label tap and speech events.
- Freeze matching tolerances before scoring.
- Report event precision/recall/F1, timing MAE, inter-rater agreement and
  performance by device and capture condition.
- Failed thresholds narrow the output; they do not trigger threshold tuning on
  the evaluation set.

### Gate 4 — clinically governed feasibility

- Only after protocol, governance and Gate 3 pass.
- Clinician and speech-language professional own task wording and interpretation.
- Patient inclusion/exclusion, adverse-event handling and withdrawal procedures
  are approved externally.
- The system remains measurement support, never diagnosis or treatment advice.

## Stress-test matrix

| Dimension | Cases | Pass condition |
|---|---|---|
| Devices | Three representative phones; front/rear cameras | Five full sessions per device without unrecoverable failure |
| Lighting | even, dim, backlit, warm/cool | Wrong conditions rejected with the correct reason |
| Hand | right/left, partial, occluded, rotated, out of zone | No wrong-hand or invalid frame is accepted |
| Motion | slow, fast, irregular, pauses, tremor-like synthetic motion | Events remain within preregistered timing/count limits or are rejected |
| Audio | quiet, noise, clipping, distance, silence | Correct deterministic QC reason and no fabricated speech event claim |
| Lifecycle | background, lock, permission loss, camera disconnect | Capture stops safely; no partial attempt is accepted |
| Storage | duplicate submit, stale key, interrupted upload, full disk | Idempotent outcome; no orphan accepted record |
| Load | 50 duplicate measurement claims and repeated sessions | One accepted result per task; stable memory and bounded latency |

## Research-module decision for face/head/eye signals

Start only with a written hypothesis such as “head angular excursion during T03
is repeatable within X degrees against a reference pose estimator.” Do not start
with “track everything.” A defensible module would have its own model assets,
typed landmark contract, quality flags, reference dataset, regression suite and
consent disclosure. It must not share acceptance thresholds with hand capture.

## Primary technical references

- Google AI Edge, MediaPipe framework graphs and timestamped calculator nodes:
  https://developers.google.com/edge/mediapipe/framework/framework_concepts/graphs
- Google AI Edge, Holistic Landmarker (543 landmarks):
  https://developers.google.com/edge/mediapipe/solutions/vision/holistic_landmarker
- Google AI for Developers, Face Landmarker options and outputs:
  https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/vision/FaceLandmarkerOptions
- Zhang et al., *MediaPipe Hands: On-device Real-time Hand Tracking*:
  https://arxiv.org/abs/2006.10214
- Lugaresi et al., *MediaPipe: A Framework for Building Perception Pipelines*:
  https://arxiv.org/abs/1906.08172
