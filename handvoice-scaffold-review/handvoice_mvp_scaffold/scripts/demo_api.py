from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from services.api.app.main import app


with TestClient(app) as client:
    participant = client.post("/v1/participants", json={"study_id": "HV-DEMO"}).json()
    session = client.post("/v1/sessions", json={"participant_id": participant["id"], "protocol_version": "1.0.0"}).json()
    print(f"Participant: {participant['id']}")
    print(f"Session: {session['id']} sequence={session['sequence_id']}")
    for task in session["tasks"]:
        print(task["order_index"], task["task_code"], task["repetition"], task["hand"], task["speech_task"])
