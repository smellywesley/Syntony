# Current architecture decisions

## ADR-001 — Three tasks only

The competition MVP tests right-hand tapping, `/pa-ta-ka/`, and their simultaneous combination. Counting, left-hand testing and longitudinal analysis are removed until the measurement is proven.

## ADR-002 — One synchronized MP4

Audio and video share one media timeline. MP4 is preferred, while WebM or MOV is accepted when required by browser recording support. Independent recorders are not accepted.

## ADR-003 — Synchronous thin path

The API performs media validation and measurement analysis synchronously. The previous sleeping worker was removed because it overstated implementation maturity.

## ADR-004 — Optional second repetition

A session creates one instance per task. Repetition 2 is scheduled only after repetition 1 passes acceptance.

## ADR-005 — Global event matching

Cross-modal events use maximum-cardinality bipartite matching, followed by minimum total absolute lag. Greedy nearest-neighbour matching is prohibited.

## ADR-006 — Merge voiced intervals

VAD intervals are clipped and merged before voiced-duration or pause calculations. Overlap cannot count twice.

## ADR-007 — Measurement before classification

Outputs are hand rhythm, DDK rhythm, bidirectional DTC and an exploratory synchronized timeline. No disease probability is produced.

## ADR-008 — Coupling is exploratory

Coupling is not the primary competition endpoint and must not be interpreted clinically. It survives only as an exploratory visualization and feature.

## ADR-009 — Coarse local security only

All `/v1` routes require an API key. Media keys are resolved inside a configured root and verified by checksum and `ffprobe`. Multi-user ownership, presigned cloud upload and clinical authorization remain future work.

## ADR-010 - Local browser landmarks

The capture app runs MediaPipe hand landmarking locally and submits timestamped frames with the synchronized media. This avoids a redundant server-side video-inference service in the validation prototype.

## ADR-011 - Engineering claims only

Synthetic perturbation tests validate deterministic software behavior against known ground truth. Without approved human-participant data, they do not validate older-adult usability, disease discrimination, clinical constructs, or diagnostic performance.
