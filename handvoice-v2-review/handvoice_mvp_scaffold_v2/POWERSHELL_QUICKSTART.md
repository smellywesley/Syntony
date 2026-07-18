# HandVoice PowerShell Quick Start

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

Expected verified test result:

```text
73 passed
```

## Docker

```powershell
Copy-Item .env.example .env
New-Item -ItemType Directory -Force .\local_media
docker compose up --build
```

PostgreSQL is internal to Docker and is not exposed on port 5432.
