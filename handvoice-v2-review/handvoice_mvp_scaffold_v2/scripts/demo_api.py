import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEMO_OPERATOR_KEY = "demo-operator-key-not-for-real-data"
os.environ.setdefault("HANDVOICE_BOOTSTRAP_KEY", DEMO_OPERATOR_KEY)

from fastapi.testclient import TestClient  # noqa: E402

from services.api.app.main import app  # noqa: E402

headers = {"Authorization": f"Bearer {os.environ['HANDVOICE_BOOTSTRAP_KEY']}"}
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
