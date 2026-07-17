import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("HANDVOICE_API_KEY", "local-development-only-change-me")

from fastapi.testclient import TestClient  # noqa: E402

from services.api.app.main import app  # noqa: E402

headers = {"X-HandVoice-API-Key": os.environ["HANDVOICE_API_KEY"]}
with TestClient(app) as client:
    participant = client.post(
        "/v1/participants", headers=headers, json={"study_id": "HV-DEMO"}
    ).json()
    session = client.post(
        "/v1/sessions",
        headers=headers,
        json={"participant_id": participant["id"], "protocol_version": "1.1.0"},
    ).json()
    print(f"Participant: {participant['id']}")
    print(f"Session: {session['id']} sequence={session['sequence_id']}")
    for task in session["tasks"]:
        print(
            task["order_index"],
            task["task_code"],
            task["repetition"],
            task["hand"],
            task["speech_task"],
        )
