# Grill Session Report - HandVoice - 17 July 2026

## Verdict

**Build the validation prototype; do not present it as a validated biomedical product.** The synchronized capture and measurement stack is executable and technically defensible, but the absence of ethics approval and human-participant data blocks claims about older adults, Parkinson's disease, clinical validity, or diagnostic performance.

The ICBME 2026 abstract deadline was 14 July 2026 and no submission was made. The current build can support a later demo, internal review, or future paper, but it cannot retroactively become an accepted ICBME 2026 submission. Official references: [Call for Abstracts](https://icbme.org.sg/2026/call-for-abstracts/) and [Conference Themes](https://icbme.org.sg/2026/themes/).

## 1. Project Summary

HandVoice measures synchronized right-hand tapping and `/pa-ta-ka/` speech during single and dual tasks. A smartphone browser captures audiovisual media and local hand landmarks; the backend verifies synchronization and integrity, extracts timing features, computes direction-aware dual-task costs, and renders a shared timeline. The research wedge is measurement of bidirectional motor-speech interference, not disease classification. The immediate evidence is deterministic software and synthetic perturbation validation. No business model is currently specified because this is a competition/research prototype.

## 2. Assumptions Discovered

| # | Assumption | Load-bearing? | Validation experiment | Deadline | Status |
|---|---|---|---|---|---|
| 1 | Older adults can complete the 3-task flow without coaching | Yes | Approved usability study measuring completion, errors and burden | Before any older-adult claim | Unvalidated |
| 2 | Browser landmarks remain accurate under real occlusion and tremor | Yes | Annotated real-video benchmark across devices and lighting | Before field use | Unvalidated |
| 3 | Energy-derived DDK events correspond to true syllable onsets | Yes | Compare against blinded human annotations | Before speech-performance claim | Unvalidated |
| 4 | Dual-task cost is repeatable within a person | Yes | Test-retest study with preregistered reliability threshold | Before longitudinal claim | Unvalidated |
| 5 | Motor-speech coupling adds value beyond single-modality rhythm | No for MVP; yes for novelty | Ablation study on approved participant data | Before coupling claim | Unvalidated |
| 6 | Deterministic tap detection is robust to basic acquisition perturbations | Yes for engineering prototype | Frozen synthetic 5-condition study, 20 seeds each | 17 Jul 2026 | Validated synthetically |

## 3. Weaknesses Found

1. **No human evidence:** the largest scientific claim gap; any biomedical efficacy wording would be misleading. Fix: obtain ethics approval and run the staged evidence ladder in the validation plan.
2. **Speech segmentation is a baseline, not phonetic validation:** energy bursts can confuse noise, breath and syllables. Fix: build an annotated DDK benchmark before claiming speech accuracy.
3. **Single API key:** acceptable for a local demo but unsuitable for participant data or multi-user deployment. Fix: scoped study accounts, authorization, retention policy and audit controls before real data.
4. **Synthetic validation is deliberately easy to interpret:** it proves invariance under specified perturbations, not ecological validity. Fix: add prerecorded bench media, then approved human data.
5. **Conference timing:** the ICBME abstract deadline has passed without submission. Fix: target the next eligible venue or contact organizers without assuming an exception.

## 4. Open Questions

1. Who is the accountable clinical/biomedical supervisor for protocol and claim review? Owner: founder. Blocks: human study.
2. Which institution can sponsor ethics review and participant recruitment? Owner: founder. Blocks: clinical evidence.
3. What is the reference standard for DDK onset and functional hand performance? Owner: clinical supervisor. Blocks: validation metrics.
4. Which phone/browser/device matrix is required? Owner: engineering. Blocks: deployment confidence.
5. Is the next target a conference demo, paper submission, or judged competition? Owner: founder. Blocks: narrative and deadline plan.

## 5. Recommended Architecture Changes

Implemented:

- Replaced manual media placement with bounded API upload and generated contained keys.
- Added local browser MediaPipe inference and a compiled capture interface.
- Enforced exact task modality contracts and frozen active-window timing.
- Added A/V start-skew and synchronized-duration checks.
- Made tap detection invariant to frame ordering and duplicate timestamps.
- Added deterministic synthetic evaluation and machine-readable output.
- Pinned top-level dependencies and removed known npm audit findings.

Do not add yet:

- Parkinson's classifier, clinical severity score, medication advice or autonomous agent decisions.
- Multi-agent orchestration; the core path is a deterministic measurement pipeline.
- Microservices, vector databases or cloud complexity without a validated need.

## 6. Recommended Product Changes

- Position as a **synchronized motor-speech measurement prototype**.
- Lead the demo with the shared timeline and dual-task comparison, not a disease label.
- Show invalid-capture rejection as a scientific-integrity feature.
- Put the evidence boundary on the first and final presentation slides.
- Keep the three-task protocol; do not reintroduce broad cognitive batteries until the wedge is validated.

## 7. Recommended Skills and Tools

| Skill/tool | Verdict | Reason |
|---|---|---|
| Coding/build workflow | Now | The scope is frozen enough for a validation prototype; code and tests now exist. |
| Testing/QA | Now | Deterministic and AI/CV-specific evaluation is the central credibility layer. |
| UX/accessibility review | Now | Older-adult usability remains untested and the flow needs expert review before recruitment. |
| Security audit | Before real data | The local API key boundary is not appropriate for participant data. |
| Research agent/web search | Now | Needed for venue rules, validated comparators and primary-source evidence. |
| Data analysis | Later | Required once approved real or annotated bench data exist. |
| Legal/compliance support | Before real data | Needed to prepare ethics, consent, retention and privacy materials for human review. |
| Presentation/deck workflow | Later | Build the deck after the target venue and honest evidence narrative are fixed. |
| Agenty automation connector | Never for core measurement | External workflow automation does not improve capture validity or biomedical evidence. |
| Multi-agent clinical decision system | Never for this MVP | Adds failure surface without solving the current evidence bottleneck. |

## 8. Execution Readiness Scorecard

| Dimension | Score /10 | Evidence or gap |
|---|---:|---|
| Problem clarity | 6 | Narrow motor-speech measurement question; user pain not observed. |
| User clarity | 4 | Older adult is a demographic, not yet a validated workflow persona. |
| Market urgency | 3 | Competition motivation exists; clinical/buyer urgency is unverified. |
| Technical feasibility | 8 | Working browser-to-API stack and perturbation harness. |
| Data availability | 2 | No approved human or annotated real-world validation set. |
| AI/CV necessity | 6 | CV reduces manual landmarking; no-AI/manual baseline still needs benchmark. |
| UX clarity | 6 | Core flow exists; no older-adult usability evidence. |
| Monetization logic | 1 | Not specified; acceptable only while treated strictly as research. |
| Competitive advantage | 4 | Synchronized wedge is interesting but no proprietary data or validated moat. |
| Build plan | 8 | Frozen tasks, contracts, tests and runtime path. |
| Evaluation plan | 6 | Synthetic thresholds exist; human endpoints do not. |
| Deployment readiness | 7 | Reproducible local Docker deployment; not clinical production. |
| Risk control | 7 | Claim boundary and failure checks are explicit; study governance absent. |

**Gating minimum: 2/10 for data availability** (or 1/10 if monetization is treated as required). Protocol verdict: proceed only with validation work, not a clinical product build.

## 9. Next Actions

1. **17 Jul 2026 - freeze engineering result:** definition of done is committed code, 33 backend tests, 2 frontend tests, lint, build, audit and synthetic JSON all green. Status: complete, pending repository commit decision.
2. **20 Jul 2026 - venue decision:** select the next submission/demo target and record its real deadline and format.
3. **24 Jul 2026 - annotated bench set:** create or lawfully source non-participant prerecorded media with blinded tap/DDK reference events.
4. **31 Jul 2026 - device matrix:** pass capture and media validation on at least three representative phones/browsers.
5. **7 Aug 2026 - protocol sponsorship:** identify biomedical/clinical supervisor and ethics-sponsoring institution.
6. **Before recruitment - ethics package:** approved protocol, consent, data inventory, retention/deletion and adverse-event plan.
7. **After approval - feasibility study:** preregister completion, missingness, timing agreement and test-retest thresholds before collecting data.

## 10. Confidence Score: 7/10 for the engineering prototype; 3/10 for conference scientific impact

The software is now executable, reproducible and unusually honest about failure boundaries. Confidence falls sharply for scientific impact because novelty alone is not evidence: no real participant workflow, annotated clinical reference, test-retest result or ethics-approved dataset exists.

## 11. Risk Score: 8/10

The largest risk is claim inflation—presenting clean synthetic results as evidence about older adults or Parkinson's disease. That would be scientifically indefensible and could damage the project more than a failed model. The mitigation is strict language, staged validation and human governance before real-data collection.

## State Delta

- Added: executable browser capture, safe media upload, synchronization checks and synthetic validation.
- Validated: deterministic tap detection under the frozen perturbation set and DTC arithmetic.
- Still assumed: older-adult usability, real-world CV/audio validity, repeatability and clinical meaning.
- Decision: remain an engineering-validation prototype; no diagnostic or agentic clinical decisions.

