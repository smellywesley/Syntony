# HandVoice PowerShell Quick Start

```powershell
# 1. Extract the ZIP, then enter the repository
cd .\handvoice_mvp_scaffold

# 2. Create and activate a virtual environment
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1

# 3. Install the project and test dependencies
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

# 4. Run the validated test suite
pytest

# 5. Run the API
uvicorn services.api.app.main:app --reload
```

Open the API documentation:

```text
http://127.0.0.1:8000/docs
```

Run the sample protocol generator in a second terminal:

```powershell
.\.venv\Scripts\Activate.ps1
python .\scripts\demo_api.py
```

## Docker alternative

```powershell
Copy-Item .env.example .env
docker compose up --build
```

## Expected current test result

```text
12 passed
```
