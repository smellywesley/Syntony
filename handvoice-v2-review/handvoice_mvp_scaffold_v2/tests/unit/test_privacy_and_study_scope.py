from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from services.api.app.core.config import get_settings
from services.api.app.db.base import Base
from services.api.app.models.entities import (
    AssessmentSession,
    AuditEvent,
    Operator,
    Participant,
    Recording,
    TaskInstance,
)
from services.api.app.services.access import (
    get_authorized_participant,
    get_authorized_session,
    get_authorized_task,
    operator_can_access_study,
    operator_owns_pending_upload,
    valid_pending_upload_key,
)
from services.api.app.services.privacy import remove_participant_data


def _operator(study_id: str | None) -> Operator:
    return Operator(
        id=uuid4(),
        label=f"operator-{study_id or 'global'}",
        study_id=study_id,
        key_hash=uuid4().hex * 2,
    )


def _database() -> tuple[object, Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine, Session(engine)


def test_study_operator_is_isolated_from_other_studies():
    _, db = _database()
    with db:
        operator_a = _operator("study-a")
        operator_b = _operator("study-b")
        participant_a = Participant(study_id="study-a")
        participant_b = Participant(study_id="study-b")
        db.add_all([operator_a, operator_b, participant_a, participant_b])
        db.flush()
        session_b = AssessmentSession(
            participant_id=participant_b.id,
            protocol_version="1.1.0",
            sequence_id="A",
            session_number=1,
        )
        db.add(session_b)
        db.flush()
        task_b = TaskInstance(
            session_id=session_b.id,
            task_code="T01",
            task_name="tap",
            condition="single",
            hand="right",
            repetition=1,
            order_index=1,
        )
        db.add(task_b)
        db.commit()

        assert get_authorized_participant(db, participant_a.id, operator_a) is not None
        assert get_authorized_participant(db, participant_b.id, operator_a) is None
        assert get_authorized_session(db, session_b.id, operator_a) is None
        assert get_authorized_task(db, task_b.id, operator_a) is None
        assert get_authorized_session(db, session_b.id, operator_b) is not None


def test_global_operator_and_upload_ownership_rules():
    global_operator = _operator(None)
    scoped_operator = _operator("study-a")
    assert operator_can_access_study(global_operator, "any-study")
    assert operator_can_access_study(scoped_operator, "study-a")
    assert not operator_can_access_study(scoped_operator, "study-b")
    owned = f"incoming/{scoped_operator.id.hex}_{uuid4().hex}.webm"
    foreign = f"incoming/{global_operator.id.hex}_{uuid4().hex}.webm"
    assert operator_owns_pending_upload(scoped_operator, owned)
    assert not operator_owns_pending_upload(scoped_operator, foreign)
    assert valid_pending_upload_key(owned)
    assert not valid_pending_upload_key("../capture.webm")
    assert not valid_pending_upload_key("incoming/not-generated.webm")


@pytest.mark.parametrize("retain_marker", [True, False])
def test_participant_privacy_deletion_removes_database_and_media(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    retain_marker: bool,
):
    monkeypatch.setenv("HANDVOICE_STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    _, db = _database()
    try:
        with db:
            operator = _operator("study-a")
            participant = Participant(study_id="study-a", external_reference="coded-1")
            db.add_all([operator, participant])
            db.flush()
            assessment = AssessmentSession(
                participant_id=participant.id,
                protocol_version="1.1.0",
                sequence_id="A",
                session_number=1,
            )
            db.add(assessment)
            db.flush()
            task = TaskInstance(
                session_id=assessment.id,
                task_code="T01",
                task_name="tap",
                condition="single",
                hand="right",
                repetition=1,
                order_index=1,
            )
            db.add(task)
            db.flush()
            media = tmp_path / "processing" / "capture.webm"
            media.parent.mkdir(parents=True)
            media.write_bytes(b"media")
            db.add(
                Recording(
                    task_instance_id=task.id,
                    object_uri=f"file://{media.resolve()}",
                    sha256="0" * 64,
                    duration_ms=15000,
                )
            )
            db.commit()
            participant_id = participant.id

            result = remove_participant_data(
                db,
                participant_id,
                operator,
                retain_withdrawn_marker=retain_marker,
            )

            assert result.deleted_session_count == 1
            assert result.deleted_recording_count == 1
            assert result.deleted_media_count == 1
            assert not media.exists()
            retained = db.get(Participant, participant_id)
            if retain_marker:
                assert retained is not None
                assert retained.status == "withdrawn"
                assert retained.external_reference is None
                assert retained.sessions == []
            else:
                assert retained is None
            audit = db.scalar(
                select(AuditEvent).where(AuditEvent.entity_id == str(participant_id))
            )
            assert audit is not None
            assert audit.action in {"participant.withdraw", "participant.delete"}
    finally:
        get_settings.cache_clear()
