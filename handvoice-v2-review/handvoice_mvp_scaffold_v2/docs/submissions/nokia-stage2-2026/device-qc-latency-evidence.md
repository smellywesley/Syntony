# Device, quality and latency evidence

Record measured values only. Do not convert this table into an older-adult or
clinical-performance claim.

## Device matrix

| Device / OS / browser | Tier | Runs attempted | Runs accepted | QC failures by reason | p50 / p95 report latency | Evidence file |
|---|---|---:|---:|---|---|---|
| OPEN | Low | | | | | |
| OPEN | Mid | | | | | |
| OPEN | High | | | | | |

Five complete demo runs per device are required. If three physical devices are
not tested, restrict all compatibility wording to the devices actually tested.
The local Docker service is loopback HTTP only. A physical phone must use HTTPS
or trusted secure-device forwarding; never expose the bearer key and media by
binding the current service directly to a LAN.

## Thirty-case QC decision-table golden set

Automated engineering result, 20 July 2026: **30/30 exact decision-and-reason
matches**. The versioned cases are in `tests/fixtures/qc_golden_v1.json` and the
enforcing test is `tests/unit/test_qc_golden.py`. They cover valid capture,
missing/out-of-guide and structurally wrong-hand inputs, low-light/valid-frame
proxies, low frame rate, quiet/clipped/no-speech audio, decode failure, A/V
offset, insufficient events and background interruption.

This injects precomputed quality metrics, so it verifies the deterministic
decision contract, not the camera/audio/media pipeline. Wrong-hand rejection is
covered by a separate structural test. The planned 30-case media-capture golden
set remains **OPEN** until licensed or purpose-made fixtures are available.

Decision-table acceptance: 30/30 exact matches. Known-good capture rejection
above 20% forces device restriction or use of the prerecorded fallback. Target
p95 record-to-report latency is ≤10 seconds; >20 seconds fails the demo gate.

## DDK annotation gate

Target: F1 ≥0.90 at 20 ms and onset MAE ≤15 ms on licensed or explicitly
consented non-clinical material. Status: **NOT RUN**. Until passed, DDK
fine-structure output is exploratory and excluded from impact claims.
