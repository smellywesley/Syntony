import os
from pathlib import Path

os.environ["HANDVOICE_DATABASE_URL"] = "sqlite:///./test_handvoice.db"
os.environ["HANDVOICE_AUTO_CREATE_SCHEMA"] = "true"
os.environ["HANDVOICE_PROTOCOL_PATH"] = "configs/protocol.v1.yaml"

from fastapi.testclient import TestClient

from services.api.app.db.base import Base
from services.api.app.db.session import engine
from services.api.app.main import app


def setup_module():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def teardown_module():
    Base.metadata.drop_all(bind=engine)
    Path("test_handvoice.db").unlink(missing_ok=True)


def test_create_participant_and_session():
    with TestClient(app) as client:
        participant_response = client.post("/v1/participants", json={"study_id": "HV-PILOT-001", "external_reference": "demo-001"})
        assert participant_response.status_code == 201
        participant_id = participant_response.json()["id"]

        session_response = client.post("/v1/sessions", json={"participant_id": participant_id, "protocol_version": "1.0.0", "context": {"fatigue_0_10": 3}})
        assert session_response.status_code == 201
        body = session_response.json()
        assert len(body["tasks"]) == 16
        assert body["sequence_id"] in {"A", "B", "C", "D"}

        report_response = client.get(f"/v1/sessions/{body['id']}/report")
        assert report_response.status_code == 200
        assert report_response.json()["task_count"] == 16
        assert "no diagnosis" in report_response.json()["note"].lower()
