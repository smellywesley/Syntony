from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from services.api.app.models.entities import (
    AssessmentSession,
    Operator,
    Participant,
    TaskInstance,
)

PENDING_UPLOAD_PATTERN = re.compile(
    r"^incoming/(?P<operator>[0-9a-f]{32})_[0-9a-f]{32}\.(?:mp4|webm|mov)$"
)


def valid_pending_upload_key(storage_key: str) -> bool:
    return PENDING_UPLOAD_PATTERN.fullmatch(storage_key) is not None


def operator_owns_pending_upload(operator: Operator, storage_key: str) -> bool:
    matched = PENDING_UPLOAD_PATTERN.fullmatch(storage_key)
    return matched is not None and matched.group("operator") == operator.id.hex


def operator_can_access_study(operator: Operator, study_id: str) -> bool:
    """Global bootstrap operators have NULL scope; study operators are isolated."""
    return operator.study_id is None or operator.study_id == study_id


def get_authorized_participant(
    db: Session,
    participant_id: UUID,
    operator: Operator,
    *,
    for_update: bool = False,
) -> Participant | None:
    statement = select(Participant).where(Participant.id == participant_id)
    if operator.study_id is not None:
        statement = statement.where(Participant.study_id == operator.study_id)
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def get_authorized_session(
    db: Session,
    session_id: UUID,
    operator: Operator,
) -> AssessmentSession | None:
    statement = (
        select(AssessmentSession)
        .join(Participant, AssessmentSession.participant_id == Participant.id)
        .options(selectinload(AssessmentSession.tasks))
        .where(AssessmentSession.id == session_id)
    )
    if operator.study_id is not None:
        statement = statement.where(Participant.study_id == operator.study_id)
    return db.scalar(statement)


def get_authorized_task(
    db: Session,
    task_id: UUID,
    operator: Operator,
) -> TaskInstance | None:
    statement = (
        select(TaskInstance)
        .join(AssessmentSession, TaskInstance.session_id == AssessmentSession.id)
        .join(Participant, AssessmentSession.participant_id == Participant.id)
        .where(TaskInstance.id == task_id)
    )
    if operator.study_id is not None:
        statement = statement.where(Participant.study_id == operator.study_id)
    return db.scalar(statement)
