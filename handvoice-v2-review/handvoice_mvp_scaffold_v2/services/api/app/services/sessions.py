from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.api.app.models.entities import AssessmentSession, Participant, TaskInstance
from services.api.app.schemas.api import SessionCreate
from services.api.app.services.protocol import choose_sequence, expand_task_instances, load_protocol


def create_session(db: Session, payload: SessionCreate) -> AssessmentSession:
    # PostgreSQL serializes session-number allocation for one participant on this row.
    participant = db.scalar(
        select(Participant).where(Participant.id == payload.participant_id).with_for_update()
    )
    if participant is None:
        raise LookupError("participant not found")

    latest_number = db.scalar(
        select(func.max(AssessmentSession.session_number)).where(
            AssessmentSession.participant_id == participant.id
        )
    )
    session_number = int(latest_number or 0) + 1
    protocol = load_protocol()
    if payload.protocol_version != protocol["protocol_version"]:
        raise ValueError("requested protocol version is not available")
    sequence_id = choose_sequence(str(participant.id), session_number, protocol)
    session = AssessmentSession(
        participant_id=participant.id,
        protocol_version=payload.protocol_version,
        sequence_id=sequence_id,
        session_number=session_number,
        context_json=payload.context,
    )
    db.add(session)
    db.flush()
    for item in expand_task_instances(protocol, sequence_id):
        db.add(
            TaskInstance(
                session_id=session.id,
                task_code=item["code"],
                task_name=item["name"],
                condition=item["condition"],
                hand=item.get("hand"),
                speech_task=item.get("speech_task"),
                repetition=item["repetition"],
                order_index=item["order_index"],
            )
        )
    db.commit()
    return db.scalar(select(AssessmentSession).where(AssessmentSession.id == session.id))
