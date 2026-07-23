# HandVoice PowerShell Quick Start

## Competition demo (recommended)

Install and start Docker Desktop, then run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_demo.ps1 -RevealKey
```

The script generates local secrets, builds the browser app and API, verifies
both endpoints and opens the capture interface. It is safe to run again and
never overwrites an existing valid `.env`. Use `-RevealKey` only in a private
terminal; omit it when screen sharing or recording.

Use demo identifiers only. Do not enter real health or personal data.

This loopback HTTP setup is for a same-computer demo. Physical-phone testing
requires HTTPS or trusted secure-device forwarding; never expose port 8000
directly to a LAN.

## Native developer setup

For a one-command localhost demo without Docker, use:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_demo_native.ps1
```

This builds the browser app, starts the API with SQLite on `127.0.0.1:8000`,
checks the health and capture endpoints, and goes directly to coded participant
setup without an operator-key prompt. Stop it with
`.\scripts\stop_demo_native.ps1`. FFmpeg and ffprobe are still required to
validate and measure recorded media; without them, only the user interface and
pre-capture workflow can be demonstrated.

```powershell
cd .\handvoice_mvp_scaffold_v2

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or
    -not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
    throw "FFmpeg and ffprobe are required. Install FFmpeg or use the Docker quick start below."
}

py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

Push-Location .\apps\capture-web
npm ci
npm run build
Pop-Location

# Seeds the first operator; a placeholder value is refused. Generate a unique secret.
$env:HANDVOICE_BOOTSTRAP_KEY = python -c "import secrets; print(secrets.token_urlsafe(32))"
$env:HANDVOICE_STORAGE_ROOT = ".local_storage"

pytest
uvicorn services.api.app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

Use this header for `/v1` routes (the operator key you generated above):

```text
Authorization: Bearer <your generated key>
```

The complete Python suite, browser tests and browser production build must pass.

## Docker

Use `scripts/start_demo.ps1`; copying `.env.example` without replacing its
placeholders will intentionally fail closed.

PostgreSQL is internal to Docker and is not exposed on port 5432.
