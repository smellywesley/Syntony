# HandVoice Competition MVP — Canonical Architecture v4

**Status:** Controlling implementation document  
**Supersedes for competition scope:** earlier broad HandVoice architecture, full longitudinal roadmap, eight-task protocol, counting protocol, clinical-classification proposals, and asynchronous-worker claims.

## 1. Core measurement hypothesis

HandVoice tests one primary hypothesis:

> When a participant performs right-hand finger tapping and repeated `/pa-ta-ka/` simultaneously, does either manual rhythm or articulatory rhythm deteriorate relative to the same tasks performed alone?

The competition MVP is not designed to diagnose Parkinson’s disease. It is a synchronized functional-measurement demonstrator.

## 2. Primary outputs

The system reports:

1. Hand tapping rate and rhythm variability
2. DDK syllable rate and rhythm variability
3. Hand dual-task cost
4. Speech dual-task cost
5. One synchronized hand-and-speech event timeline

Temporal coupling is retained only as an exploratory output. It is not the primary endpoint.

## 3. Frozen protocol

The first-pass session contains exactly three recordings:

| Code | Task | Condition |
|---|---|---|
| T01 | Right-hand index–thumb tapping | Single hand |
| T02 | Repeated `/pa-ta-ka/` | Single speech |
| T03 | Right-hand tapping plus `/pa-ta-ka/` | Dual |

Each recording is one synchronized audiovisual media file. MP4 is preferred; WebM or MOV is accepted when the browser cannot emit MP4:

```text
2-second pre-roll
10-second active measurement window
3-second post-roll
```

The dual task is always performed after both single-task baselines. The order of T01 and T02 may be counterbalanced.

The initial session creates only one instance of each task. A second repetition is created only after the first recording is accepted. This keeps the first participant burden to three recordings and prevents an automatic 16-recording session.

## 4. Explicit exclusions

The competition implementation does not include:

- Backwards counting
- Left-hand assessment
- Longitudinal baselines
- Minimum detectable change
- Passive phone-call monitoring
- Clinical severity prediction
- Parkinson’s classification
- Medication recommendations
- Agentic threshold decisions
- Production multi-tenant authorization

These may remain future research directions but cannot distract from proving the synchronized measurement.

## 5. Executable system path

```text
capture synchronized camera + microphone media in the browser
        ↓
derive MediaPipe hand landmarks locally, then upload to a generated contained key
        ↓
validate audio/video tracks with ffprobe
        ↓
derive hand signal from landmark frames
        ↓
detect tapping events and hand rhythm
        ↓
decode audio or consume validated DDK annotations
        ↓
derive voice intervals and DDK rhythm
        ↓
calculate bidirectional dual-task cost
        ↓
persist events and features
        ↓
render synchronized HTML timeline
```

The API performs this path synchronously. No background queue is advertised in the competition version.

## 6. Detector and evidence boundary

The hand-analysis service consumes 21-point hand-landmark frames. It converts the landmarks into:

- Thumb–index distance normalized by palm scale
- Thumb–wrist–index angle
- Candidate tap-opening events
- Tapping rate
- Inter-tap interval variability
- Median normalized amplitude

The capture app performs MediaPipe hand-landmark inference locally in the browser and submits timestamped landmark frames with the recording. Server-side raw-video landmark inference is deliberately not duplicated in this prototype.

The audio service can decode the active segment from the media file and apply a conservative energy-based baseline for voiced intervals and candidate syllable onsets. It can also consume manually or externally validated DDK onset annotations. The energy detector is an executable baseline, not a clinically validated DDK segmenter.

No human-participant dataset or ethics approval is currently available. The implementation can therefore support engineering-validation claims only; it cannot support claims about older adults, Parkinson's disease, clinical validity, diagnostic accuracy, or biomedical outcomes.

## 7. Dual-task cost

For measurements where higher is better:

```text
DTC = 100 × (single − dual) / |single|
```

Examples:

- Tapping rate
- DDK syllable rate

For measurements where lower is better:

```text
DTC = 100 × (dual − single) / |single|
```

Examples:

- Inter-tap interval CV
- DDK interval CV

Positive DTC always means deterioration. A near-zero single-task baseline makes percentage DTC unavailable rather than infinite or misleading.

The primary competition result is the pair:

```text
hand rhythm DTC
speech rhythm DTC
```

## 8. Exploratory event coupling

Hand openings and DDK onsets are represented as timestamped events on the same 10-second time axis.

The matching algorithm must:

1. Find the maximum possible number of valid one-to-one pairs within the configured time window.
2. Among maximum-cardinality solutions, minimize total absolute lag.
3. Use deterministic tie-breaking.

A greedy nearest-neighbour algorithm is prohibited because it can select one locally close pair and block two valid global pairs.

The current implementation uses ordered dynamic programming, which is equivalent to maximum-cardinality matching followed by minimum total lag for the one-dimensional time-ordered event problem.

Coupling remains exploratory because:

- Coincidence can occur by chance
- Event extraction error affects the result
- Participants may unintentionally synchronize rhythms
- Reliability has not been established
- Clinical meaning is unknown

## 9. Speech timing integrity

Voice intervals are clipped to the active window, sorted, and merged before calculating:

- Voiced duration
- Speech onset
- Pause percentage
- Mean pause duration
- Maximum pause duration

Overlapping VAD segments cannot contribute duplicate voiced milliseconds.

## 10. Hand-data integrity

Malformed landmark frames must become quality failures rather than exceptions.

The extractor checks:

- Minimum landmark count
- Three-dimensional coordinates
- Non-zero palm scale
- Finite geometry
- Frame validity classification

Invalid frames produce an invalid signal sample with a reason code.

## 11. Session integrity

Session numbering is protected by two controls:

1. The participant row is locked while the next session number is allocated in PostgreSQL.
2. The database enforces a unique constraint on `(participant_id, session_number)`.

Task repeats are protected by a unique constraint on:

```text
(session_id, task_code, repetition)
```

## 12. Protocol integrity

The YAML protocol is checked using:

- JSON Schema validation
- Unique task-definition codes
- Unique task-definition names
- Exact sequence length
- Exact task-code frequency using counters
- Requirement that the dual task occurs after the baselines

Set comparison alone is insufficient because it ignores duplicates.

## 13. Sensitive-media boundary

The competition API uses a coarse local security boundary:

- All `/v1` endpoints require `X-HandVoice-API-Key`.
- Clients submit a relative storage key, not an arbitrary URI.
- The resolved path must remain inside the configured media root.
- The media file must exist.
- SHA-256 must match.
- `ffprobe` must confirm both audio and video tracks.
- Recording duration and stream timing metadata are validated.

This is acceptable only for a local competition prototype. It is not a production clinical authorization model. Production deployment would require participant/study ownership, presigned uploads, token scopes, audit policy, retention controls, and security review.

## 14. Infrastructure scope

The local Docker stack contains:

- API
- PostgreSQL

PostgreSQL is not exposed to the host. Redis and the nonfunctional worker are removed. The API binds only to localhost by default.

## 15. Visualization

The session visualization is a synchronized 10-second timeline containing:

- Hand opening events
- DDK onset events
- Hand DTC values
- Speech DTC values
- Exploratory event coincidence rate

The visualization is intended to demonstrate measurement transparency. It does not display a disease score.

## 16. Acceptance criteria

The competition prototype is ready for demonstration only when:

- Three first-pass tasks are created, not 16
- API authorization is enforced
- Session numbers cannot duplicate
- Media paths cannot escape the configured root
- Checksums are verified
- A/V tracks are validated
- A/V start skew is at most 100 ms and the active window is contained in synchronized media
- Browser capture uses the frozen 2/10/3-second timing protocol
- Media uploads are bounded and use server-generated storage keys
- Overlapping voice intervals do not inflate voiced duration
- Malformed landmark frames do not crash extraction
- Coupling maximizes match cardinality before lag minimization
- Hand and speech DTC can be computed from the three tasks
- A synchronized visualization is rendered
- Automated tests pass

## 17. Current verified implementation status

The revised validation prototype has passed 33 automated backend and integration tests, plus 2 capture-web tests, covering:

- Authentication
- Three-task protocol creation
- Session sequence rotation
- Synchronous measurement processing
- Conditional repeat creation
- Path-escape rejection
- Media probing and checksums through the integration path
- Direction-aware DTC
- Maximum-cardinality event matching
- Overlapping VAD interval merging
- Raw-audio energy event extraction
- Malformed landmark handling
- Protocol duplicate rejection
- Synchronized visualization
- Task-specific modality contracts
- Active-window drift and A/V start-skew rejection
- Bounded upload and partial-file cleanup
- Tap detection invariance to submission order and duplicate timestamps
- Synthetic perturbation validation against known event ground truth

## 18. Next research gate

Do not add infrastructure until the following pilot is complete:

```text
30–50 participants
three tasks per first-pass session
manual tap-event annotation subset
manual DDK-onset annotation subset
repeat session for reliability
```

The next decision is not whether to add more features. It is whether the core outputs are measurable and repeatable:

```text
hand rate DTC
hand rhythm DTC
speech rate DTC
speech rhythm DTC
```

Only after those pass should temporal coupling, additional task types, longitudinal monitoring, or clinical cohorts expand.
