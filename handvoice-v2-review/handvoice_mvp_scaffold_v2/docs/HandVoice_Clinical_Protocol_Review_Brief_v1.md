# HandVoice Clinical Protocol Review Brief v1

## Purpose

HandVoice is an **engineering-validation prototype** for synchronized
hand–speech dual-task measurement (see `HandVoice_Conference_Validation_Plan_v1.md`).
The engineering pipeline now computes reliability (ICC/SEM/MDC), tapping
sequence-effect features, DDK onset-agreement, and per-capture confounds. Several
protocol and instruction choices sit **upstream** of those measures and are
clinical-construct decisions that the engineering team should not make alone.

This brief lists each open decision with its current state, research-backed
options, and the measurement consequence of each choice, so a movement-disorders
neurologist and a speech-language pathologist (SLP) can decide efficiently. It
proposes no clinical conclusions and grants no diagnostic claim.

**Owners:** `[Neuro]` = movement-disorders neurologist, `[SLP]` = speech-language
pathologist, `[Eng]` = engineering (implements once decided).

---

## D1 — Tapping instruction `[Neuro]`

- **Current:** capture app says *"tap at a comfortable steady pace."*
- **Options:**
  - (a) Keep "comfortable steady pace."
  - (b) Adopt MDS-UPDRS 3.4 wording: *"tap the index finger on the thumb as
    quickly AND as big as possible,"* 10+ taps.
- **Measurement consequence:** the sequence effect (amplitude/velocity decrement)
  — now computed and persisted — is elicited under the "big and fast"
  instruction. "Comfortable pace" likely suppresses the very sign the tool is
  most sensitive to. Changing wording changes what the amplitude-decrement slope
  and ratio mean; any pre-change captures are not comparable.
- **Decision:** ________________________

## D2 — Anchor tapping scoring to MDS-UPDRS 3.4? `[Neuro]`

- **Current:** continuous features only (rate, CV, decrement); no ordinal anchor.
- **Options:** (a) features only; (b) also collect a clinician 0–4 MDS-UPDRS 3.4
  rating per capture as a reference label.
- **Measurement consequence:** an ordinal anchor is what later turns
  "measurement" into "screening" (enables sensitivity/specificity work). Without
  a reference standard the tool stays a measurement instrument (correct for now).
- **Decision:** ________________________

## D3 — DDK instruction and sequencing scoring `[SLP]`

- **Current:** *"repeat pa-ta-ka clearly and steadily";* detector finds energy
  onsets only (cannot distinguish pa/ta/ka).
- **Options:**
  - (a) Keep "clearly and steadily."
  - (b) Standard SMR wording: *"as fast and as steadily as you can."*
  - (c) Decide whether pa/ta/ka **sequencing accuracy** is in scope (requires
    phoneme-level segmentation / forced alignment, not the energy detector).
- **Measurement consequence:** "as fast as you can" raises rate but can reduce
  segmentability; the whole rationale for /pa-ta-ka/ over /pa-pa-pa/ is
  articulatory switching, which the current detector cannot verify. See
  `HandVoice_DDK_Annotation_Protocol_v1.md` for the agreement gate before any DDK
  feature is reported.
- **Decision:** ________________________

## D4 — Repetitions per task `[Neuro] [SLP]`

- **Current:** `initial_repetitions = 1` (`configs/protocol.v1.yaml`); repeat is
  optional after an accepted capture.
- **Options:** (a) keep 1; (b) require ≥2 first-pass repetitions.
- **Measurement consequence:** the reliability module (ICC/SEM/MDC) and the
  `robust_condition_estimate` median are only meaningful with ≥2 repetitions —
  with 1, the "robust median" is just the single value. This is the direct
  trade-off between participant burden and intra-session reliability.
- **Decision:** ________________________

## D5 — Rest-hold segment for a tremor proxy `[Neuro]`

- **Current:** landmarks are sampled only inside the active task window; no
  rest-hold capture, so a rest-tremor proxy is **not computable** (documented in
  `pipelines/quality/confounds.py`).
- **Options:** (a) no rest task; (b) add a short rest-hold segment (e.g. hand at
  rest before the active window) to enable a resting-instability proxy.
- **Measurement consequence:** rest tremor is a distinct parkinsonian sign; a
  rest-hold segment would let the confound/feature set include a resting-motion
  estimate. Adds capture time and a new protocol state.
- **Decision:** ________________________

## D6 — Capture frame rate `[Neuro] [Eng]`

- **Current:** browser targets one landmark sample every 30 ms (~33 fps), but
  achieved rate is measured per capture and remains device-dependent. QC accepts
  ≥24 fps, reviews 20–24 fps and retries ≤20 fps.
- **Options:** (a) retain the ~33 fps target and restrict unsupported devices;
  (b) target 60 fps on validated devices; (c) revise thresholds only with
  measurement evidence.
- **Measurement consequence:** tapping may reach 3–6 Hz, so lower achieved rates
  reduce samples per cycle and degrade peak timing and amplitude estimates.
  Fifteen fps remains a tested synthetic degradation scenario, not the current
  capture target. Any threshold change needs clinician and engineering review.
- **Decision:** ________________________

---

## References

- Koo & Li (2016), *A Guideline of Selecting and Reporting Intraclass
  Correlation Coefficients for Reliability Research*, J Chiropr Med 15(2):155–163.
- Goetz et al. (2008), *MDS-UPDRS* — Item 3.4 finger tapping (speed, amplitude,
  hesitations, decrement over the sequence).
- npj Parkinson's Disease (2026), video-based finger-tapping quantification;
  Scientific Reports (2024), time-resolved fine hand movement quantification.
- Segal et al. (2022), *DDKtor: Automatic Diadochokinetic Speech Analysis*;
  Rowe et al. (2022), automatic DDK validation across dysarthria severity in ALS.
- Sensors 2022 (MDPI 22:7992), high-frame-rate MediaPipe hand movement analysis;
  MediaPipe-vs-standard 2D tracking (PMC11683656).

*All thresholds and options above are provisional engineering framings; final
construct decisions rest with the clinician and SLP.*
