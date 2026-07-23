from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from uuid import UUID

from services.api.app.core.security import require_operator
from services.api.app.db.session import get_db
from services.api.app.models.entities import Operator, Participant
from services.api.app.schemas.api import (
    ParticipantCreate,
    ParticipantRead,
    PrivacyDeletionRead,
)
from services.api.app.services.access import operator_can_access_study
from services.api.app.services.audit import add_audit_event
from services.api.app.services.media import MediaCleanupError
from services.api.app.services.privacy import remove_participant_data

router = APIRouter(
    prefix="/v1/participants",
    tags=["participants"],
)


@router.post("", response_model=ParticipantRead, status_code=status.HTTP_201_CREATED)
def create_participant(
    payload: ParticipantCreate,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_operator),
) -> Participant:
    if not operator_can_access_study(operator, payload.study_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="operator is not authorized for the requested study",
        )
    participant = Participant(study_id=payload.study_id, external_reference=payload.external_reference)
    db.add(participant)
    try:
        db.flush()
        add_audit_event(
            db,
            operator,
            action="participant.create",
            entity_type="participant",
            entity_id=participant.id,
            details={"study_id": participant.study_id},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="external_reference already exists") from exc
    db.refresh(participant)
    return participant


@router.post(
    "/{participant_id}/withdraw",
    response_model=PrivacyDeletionRead,
)
def withdraw_participant(
    participant_id: UUID,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_operator),
) -> PrivacyDeletionRead:
    try:
        result = remove_participant_data(
            db,
            participant_id,
            operator,
            retain_withdrawn_marker=True,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MediaCleanupError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "privacy_cleanup_failed",
                "message": str(exc),
            },
        ) from exc
    return PrivacyDeletionRead(
        participant_id=result.participant_id,
        deleted_session_count=result.deleted_session_count,
        deleted_recording_count=result.deleted_recording_count,
        deleted_media_count=result.deleted_media_count,
        participant_retained_as_withdrawn=result.participant_retained_as_withdrawn,
    )


@router.delete(
    "/{participant_id}",
    response_model=PrivacyDeletionRead,
)
def delete_participant(
    participant_id: UUID,
    confirm: bool = Query(default=False),
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_operator),
) -> PrivacyDeletionRead:
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="hard deletion requires confirm=true",
        )
    try:
        result = remove_participant_data(
            db,
            participant_id,
            operator,
            retain_withdrawn_marker=False,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MediaCleanupError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "privacy_cleanup_failed",
                "message": str(exc),
            },
        ) from exc
    return PrivacyDeletionRead(
        participant_id=result.participant_id,
        deleted_session_count=result.deleted_session_count,
        deleted_recording_count=result.deleted_recording_count,
        deleted_media_count=result.deleted_media_count,
        participant_retained_as_withdrawn=result.participant_retained_as_withdrawn,
    )
