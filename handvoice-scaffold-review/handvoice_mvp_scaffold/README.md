# HandVoice MVP Scaffold

Research-grade starter repository for synchronized hand–speech dual-task measurement.

## Included

- FastAPI backend with SQLAlchemy persistence
- Versioned protocol YAML and JSON Schema
- Deterministic session/task sequence generation
- Direction-aware dual-task cost engine
- One-to-one temporal event coupling engine with permutation null
- Media/video/audio pipeline contracts
- React Native-compatible protocol state machine in TypeScript
- Docker Compose for PostgreSQL, Redis, API, and worker
- Unit and API integration tests

## Clinical boundary

This repository implements measurement infrastructure. It does **not** diagnose Parkinson's disease, recommend medication, or produce a clinical disease probability.

## Quick start

```powershell
cd handvoice_mvp_scaffold
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
uvicorn services.api.app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Docker

```powershell
docker compose up --build
```

## Core API flow

1. `POST /v1/participants`
2. `POST /v1/sessions`
3. Capture each task according to the returned sequence
4. `POST /v1/task-instances/{task_instance_id}/complete`
5. Processing workers persist events/features
6. `GET /v1/sessions/{session_id}/report`

## Repository map

```text
apps/mobile/                 TypeScript protocol controller
configs/                     Frozen protocol configuration
packages/protocol_schema/    JSON Schema and shared contracts
pipelines/                   Deterministic analytics modules
services/api/                FastAPI application
services/worker/             Processing orchestration skeleton
tests/                       Unit and integration tests
```

## Deliberately not implemented yet

- Production camera and microphone native bridges
- MediaPipe runtime inference
- Automatic speech recognition model
- Cloud object-storage provider integration
- Validated clinical thresholds
- Longitudinal alerts

These are represented by stable contracts so they can be added without changing the research data model.
