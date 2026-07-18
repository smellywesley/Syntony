# HandVoice Track B — Scalability & Capability Roadmap (v1)

Track B is the engineering work that can proceed **without** ethics approval or
human-participant data. It runs in parallel with Track A (governance, ethics,
recruitment). This document records the current engineering grill, what shipped,
and the prioritized next steps, including the public datasets and neurophysiology
that should anchor the work.

## 1. Engineering grill — what is (and is not) AI / CV today

| Signal | Current implementation | Is it AI/ML? | Gap |
|---|---|---|---|
| Hand tracking | MediaPipe `HandLandmarker` in-browser → 21 keypoints/frame | **Yes** — a trained neural net produces the keypoints | Intelligence stops at keypoints; downstream is hand-written geometry (thumb–index angle, normalized distance). No learned tap model. |
| Tap / rhythm features | Deterministic geometry over keypoints (`pipelines/video/extractor.py`) | No | No learned bradykinesia/severity model. |
| Voice timing | Energy/RMS thresholding + peak picking (`pipelines/audio/media.py`) | No | Loudness stopwatch only. |
| Voice **tone / inflection / quality** | **Not measured at all** | No | No pitch (F0), jitter, shimmer, HNR, formants, or MFCCs — the classic PD voice biomarkers. |
| Diagnostic output | None (measurement only, by design) | No | Deliberate boundary; not a gap to close pre-evidence. |

**Bottom line:** the CV side is AI-backed but shallow; the voice side has no
acoustic intelligence. Adding real acoustic voice features is pure DSP on audio
already captured — no ethics approval needed — and is the highest-value Track B
capability add.

## 2. Shipped in this iteration (multi-user auth)

- Removed the single global API key. Auth now validates against a hashed,
  per-operator/site `operators` table (`Authorization: Bearer`; legacy header
  still accepted). Keys are revocable per operator.
- Bootstrap seeding (`HANDVOICE_BOOTSTRAP_KEY`) creates the first operator;
  the API otherwise fails closed.
- Capture app stores the operator key once per device (localStorage);
  **participants never enter a credential**.

### Acoustic voice features (shipped in this iteration)
`pipelines/audio/acoustic.py` adds a dependency-light (numpy-only) acoustic
baseline computed from the decoded active-window waveform for T02/T03 and
persisted under the speech modality:
- Mean F0 and F0 variability (`f0_std_hz`, `f0_range_hz`) — pitch monotonicity
- Local jitter and local shimmer (frame-to-frame period/amplitude perturbation)
- Harmonics-to-noise ratio (Boersma-style, window-normalized autocorrelation)
- `voiced_fraction` logged as a capture confound

It is flagged `validated: false` in feature metadata: F0 is tracked by short-time
autocorrelation (not glottal-cycle analysis), and jitter/shimmer are classically
measured on sustained phonation rather than DDK. Validation against Praat and
human-labeled audio remains a Track A dependency.

## 3. Prioritized next steps

### DDK temporal fine structure (shipped in this iteration)
`compute_ddk_dynamics` in `pipelines/measurement/core.py` adds, for T02/T03,
persisted under the speech modality:
- Inter-onset interval mean/SD (`ddk_ioi_mean_ms`, `ddk_ioi_sd_ms`)
- Instantaneous-rate variance (`ddk_rate_variance_hz2`) — the "variance in rate" marker
- Inter-syllable dwell time mean/SD from voiced-interval gaps (`ddk_dwell_time_*`)
- Rate-decrement slope (`ddk_rate_decrement_slope`) — the speech analogue of the
  motor sequence effect (negative = cadence slowed over the trial)

Dwell time depends on the resolution of the voiced-interval segmentation, which
is still the energy baseline; it sharpens once the DDK segmenter is validated.

### 3.1 Acoustic / DDK features — remaining work
- Validate the acoustic baseline against Praat/parselmouth on labeled audio.
- Validate DDK onset/dwell segmentation against human annotation (see the DDK
  annotation protocol doc) so dwell-time resolution is defensible.
- Consider a sustained-vowel task for defensible jitter/shimmer (protocol change).

### 3.2 Sequence-effect emphasis (align to neurophysiology)
Established work (Journal of Neurophysiology) attributes repetitive-tapping
deterioration near 2 Hz to disordered supraspinal drive in the basal ganglia,
not peripheral fatigue. The **amplitude-decrement slope** (already scaffolded in
`pipelines/measurement/core.py`) is the true differentiating marker between
Parkinson's and atypical parkinsonisms — keep it central and validate it
against labeled data.

### 3.3 Annotated benchmark from public data (do not build from scratch)
Validate the detectors against real, human-labeled ground truth using publicly
disclosed datasets:
- **FINGER-TAPPING-PARKINSONISMS-DATABASE** (GitHub): 3D gyroscope from thumb/index
  sensors, PD vs. MSA vs. PSP performing the UPDRS tapping task.
- **Parkinson's Disease Digital Biomarker DREAM Challenge**: crowdsourced raw
  accelerometer/gyroscope, benchmarked for tremor/dyskinesia/bradykinesia severity.
- **Tappy Keystroke Dataset** (Kaggle): natural keystroke timing/hesitation, 200+
  subjects (PD and controls).
- **Kaggle Finger Tapping Video Dataset**: 240-fps smartphone video with
  thumb/index trajectories labeled via DeepLabCut.

### 3.4 Device / hardware capability matrix
Validate capture and landmark accuracy across ≥3 representative phones,
lighting, and occlusion. Note the **TapTalk** finding: finger tapping tracked
well, but DDK/speech reliability dropped sharply on consumer-grade microphones
vs. clinical hardware — quantify this before trusting field audio.

### 3.5 Older-adult usability (highest-risk assumption — sequence it)
1. **Phase 1 — De-risk UI/UX:** PD users register accidental swipes when
   attempting taps and struggle with accuracy even with oversized (10–14 cm)
   buttons. Strip the UI to the absolute minimum.
2. **Phase 2 — Hardware audit:** test sensor limits across device tiers
   (especially the microphone gap above).
3. **Phase 3 — In-home adherence pilot:** 7-day remote pilot only after UI and
   hardware are verified; algorithms behave differently at home vs. under a
   clinician's eye. This phase is what motivates one-time, session-scoped
   capture links (the next auth increment beyond remember-key-on-device).

## 4. Explicit non-goals (unchanged)
No Parkinson's classifier, severity score, medication advice, or autonomous
clinical decision until Track A produces ethics-approved, human-labeled data.
The bottleneck is evidence, not features.
