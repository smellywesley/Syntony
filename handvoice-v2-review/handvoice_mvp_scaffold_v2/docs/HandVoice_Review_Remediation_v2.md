# HandVoice Scaffold Review Remediation v2

## Outcome

The reviewer’s recommendation was accepted: the competition MVP is reduced to three tasks and the implementation is centered on the core measurement path.

## Critical findings

| Finding | Resolution |
|---|---|
| Greedy coupling undercounts valid matches | Replaced by ordered dynamic programming that maximizes match cardinality, then minimizes total absolute lag. Added adversarial regression test. |
| Overlapping speech intervals double-counted | Added clipping and interval union before voiced-duration and pause calculations. Added overlap regression test. |
| Session number race | Participant row is selected `FOR UPDATE` during allocation; database unique constraint added on `(participant_id, session_number)`. |
| Protocol did not enforce exactly once | Added Draft 2020-12 JSON Schema validation and semantic `Counter` checks for exact length and exact frequency. |
| Worker did not process anything | Removed worker from Docker and replaced the infinite loop with a fail-fast archived module. Measurement runs synchronously through the API. |
| Hand extraction could crash | Added malformed-count, coordinate, palm-scale and finite-geometry checks. Invalid frames produce reason-coded invalid samples. |
| Sensitive-media API boundaries absent | Added API-key protection, contained storage keys, path traversal rejection, SHA-256 verification and `ffprobe` A/V validation. This remains a local prototype boundary, not production authorization. |
| PostgreSQL and Redis exposed | Removed Redis and worker. PostgreSQL has no host port. API binds to localhost. Credentials are environment-driven and explicitly local-only. |

## Product and research scope

Removed from the competition MVP:

- Counting
- Left-hand tasks
- Longitudinal engine
- Clinical classification
- Automatic 16-recording sessions

Frozen tasks:

1. Right-hand tapping
2. `/pa-ta-ka/`
3. Simultaneous right-hand tapping and `/pa-ta-ka/`

The first session creates three recordings. Repetition 2 is created only after an accepted first recording.

## Executable path

```text
contained MP4 + checksum
→ ffprobe validation
→ hand signal from landmark frames
→ raw-audio baseline or supplied DDK events
→ hand and speech rhythm features
→ bidirectional DTC
→ exploratory globally matched coupling
→ synchronized HTML visualization
```

## Documentation control

The controlling document is now:

```text
HandVoice_Canonical_Competition_MVP_v4.md
```

Research papers are isolated in:

```text
HandVoice_Evidence_Appendix_v1.md
```

Earlier broad system documents are superseded for competition implementation.

## Verification

```text
22 passed
```

The test suite covers the specific review failures, API authorization, media-path containment, synchronous analysis, report generation, DTC, visualization and conditional repeats.

## Remaining honest limitations

- Raw-video MediaPipe inference is not implemented in the default installation; the hand service consumes 21-point landmark frames.
- The raw-audio energy detector is an executable baseline, not a validated DDK onset detector.
- API-key security is suitable only for a local prototype.
- Coupling remains exploratory and has not demonstrated reliability or clinical meaning.
