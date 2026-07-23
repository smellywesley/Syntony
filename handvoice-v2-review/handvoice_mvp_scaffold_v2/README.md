# HandVoice Competition MVP

A deliberately narrow, executable scaffold for testing one measurement hypothesis:

> Can synchronized right-hand tapping and `/pa-ta-ka/` produce measurable, bidirectional within-session contrasts under simultaneous task loading?

## Frozen scope

The default session creates **three first-pass recordings only**:

1. Right-hand tapping alone
2. `/pa-ta-ka/` alone
3. Right-hand tapping plus `/pa-ta-ka/`

A second repetition is optional and can be created only after the first capture is accepted.

Excluded from this competition MVP:

- Counting tasks
- Left-hand testing
- Longitudinal analytics
- Clinical classification
- Medication guidance
- Autonomous diagnostic claims

Temporal coupling remains **exploratory**.

## What is executable

- Operator-key-protected FastAPI endpoints (per-operator/site keys, hashed and revocable; patients never enter a key)
- Race-safe participant session numbering in PostgreSQL
- Protocol validation through JSON Schema and exact-frequency semantic checks
- Local media path containment, SHA-256 verification and `ffprobe` validation
- Hand-signal derivation from 21-landmark frames
- Tap-event and rhythm extraction
- Raw-audio energy/VAD baseline or supplied annotated DDK events
- Acoustic voice features (F0 mean/variability, local jitter, local shimmer, HNR) via autocorrelation pitch tracking
- DDK temporal fine structure (inter-onset interval mean/SD, inter-syllable dwell time, instantaneous-rate variance, rate-decrement slope)
- Overlap-safe speech timing features
- Direction-aware bidirectional dual-task cost
- Maximum-cardinality, minimum-total-lag event matching
- Exploratory event coincidence
- Synchronized HTML timeline visualization
- Smartphone-browser camera/microphone capture with local MediaPipe hand landmarks
- Bounded, generated-key media upload with SHA-256 integrity metadata
- Deterministic synthetic perturbation validation with machine-readable results
- Optional repeat scheduling after accepted capture
- PostgreSQL/SQLite persistence

## Important evidence boundary

The browser capture app performs MediaPipe hand-landmark inference locally and submits landmarks with the synchronized recording. Raw audio can be decoded and processed by the baseline energy detector. This is an **engineering-validation prototype**: it has no human-participant evidence and makes no claim of clinical validity, Parkinson's detection, or performance in older adults.

## API flow

```text
POST /v1/participants
POST /v1/sessions
POST /v1/media
POST /v1/task-instances/{id}/measure
GET  /v1/sessions/{id}/report
GET  /v1/sessions/{id}/visualization
POST /v1/task-instances/{id}/repeat   # optional after acceptance
POST /v1/participants/{id}/withdraw   # remove sessions/media; retain withdrawn marker
DELETE /v1/participants/{id}?confirm=true  # hard-delete participant, sessions, and media
```

All `/v1` endpoints require an operator key, validated against the `operators`
table (hashed, per-operator/site, revocable):

```text
Authorization: Bearer <operator key>
```

The legacy `X-HandVoice-API-Key: <operator key>` header is still accepted for
backward compatibility. The capture app keeps the operator key in memory only
for the active browser session and clears it when the operator ends the session,
so participants never enter a credential and shared devices do not retain it.

## Recommended competition demo

The Docker-first launcher builds the capture app, bundles FFmpeg, generates
local secrets, waits for the API, checks `/health` and `/capture/`, and can
reveal the operator key in a private terminal:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_demo.ps1 -RevealKey
```

Docker Desktop is the only host prerequisite. Use synthetic/demo identifiers
only; do not enter real health or personal data. The first build may take
several minutes. A prepared machine normally starts in under two minutes.
Omit `-RevealKey` when the terminal is being shared or recorded.

If Docker Desktop is unavailable, start the same capture interface against a
native SQLite API:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_demo_native.ps1
```

The native demo goes directly to coded participant setup; no operator key is
entered in the browser. Stop it with `.\scripts\stop_demo_native.ps1`. The
native route requires the Python dependencies and Node.js; FFmpeg/ffprobe are
additionally required for recorded-media validation and the final report.

The stack binds to loopback HTTP for a same-computer demonstration. Do not
change it to a LAN-wide binding for phone testing: bearer keys and recordings
require HTTPS or a trusted secure-device forwarding path.

## Native developer setup

**Prerequisites:** Python 3.11+ and FFmpeg. `ffprobe`/`ffmpeg` must be on `PATH` — media validation, audio extraction, and 4 integration tests hard-require them (`winget install Gyan.FFmpeg` on Windows, `apt install ffmpeg` on Debian/Ubuntu).

```powershell
cd handvoice_mvp_scaffold_v2
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Push-Location .\apps\capture-web
npm ci
npm run build
Pop-Location
$env:HANDVOICE_BOOTSTRAP_KEY = python -c "import secrets; print(secrets.token_urlsafe(32))"
pytest
uvicorn services.api.app.main:app --reload
```

`HANDVOICE_BOOTSTRAP_KEY` seeds the first operator on startup so a fresh
deployment is reachable; the API always fails closed without a valid operator
key, and the server refuses to seed a known placeholder value. Provision
additional operators (per site/clinician) as their own rows, each independently
revocable. Study-scoped operators are enforced at participant, session, task,
report, and upload boundaries; a scoped key cannot access another study.

Apply versioned database migrations before starting a non-demo API:

```powershell
alembic upgrade head
```

Docker performs this migration automatically. `HANDVOICE_AUTO_CREATE_SCHEMA`
remains a local-demo convenience and is disabled in the Docker API.

Open `http://127.0.0.1:8000/capture/` for the capture interface or `http://127.0.0.1:8000/docs` for the API.

## Verified baseline

```text
Python and browser tests pass; the capture-web production build succeeds.
```

The test suite includes adversarial regression tests for the greedy coupling failure, overlapping VAD intervals, duplicate protocol codes, malformed hand landmarks, A/V start skew, active-window drift, storage-path escape, bounded and operator-owned uploads, cross-study authorization, withdrawal/deletion of database and media records, loopback-only demo authentication, placeholder-bootstrap-key seeding refusal, synchronous measurement, DTC, visualization, conditional repeat creation, duplicate-recording rejection, within-session repeatability (ICC/SEM/MDC), tapping sequence-effect features, DDK onset agreement, DDK temporal fine structure (rate variance, dwell time, rate-decrement slope), capture confounds, acoustic voice features (F0/jitter/shimmer/HNR against synthetic tones), and the synthetic validation harness.

## Engineering validation

```powershell
python scripts/run_synthetic_validation.py
```

This tests known synthetic tap-event ground truth under frame-rate, jitter, noise, dropout, duplicate-timestamp and ordering perturbations. It validates software behavior only; see `docs/HandVoice_Conference_Validation_Plan_v1.md` for the claim boundary and human-evidence ladder.

## Docker

The Docker configuration is **local competition development only**. PostgreSQL is not published to the host, Redis and the nonfunctional worker have been removed, and the API binds to `127.0.0.1:8000`.

Use `scripts/start_demo.ps1`. It refuses placeholder secrets and does not
overwrite an existing valid `.env`.

## Canonical documentation

- `docs/HandVoice_Canonical_Competition_MVP_v4.md` — controlling scope and architecture
- `docs/HandVoice_Evidence_Appendix_v1.md` — research evidence only
- `docs/api-flow.md` — executable route sequence
- `docs/architecture-decisions.md` — current ADRs

- `docs/HandVoice_Conference_Validation_Plan_v1.md` - frozen non-clinical validation and claim boundary

Earlier broad architecture documents are superseded for competition implementation.
