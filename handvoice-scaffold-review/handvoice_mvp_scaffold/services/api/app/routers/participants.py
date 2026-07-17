from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.app.db.session import get_db
from services.api.app.models.entities import Participant
from services.api.app.schemas.api import ParticipantCreate, ParticipantRead

router = APIRouter(prefix="/v1/participants", tags=["participants"])


@router.post("", response_model=ParticipantRead, status_code=status.HTTP_201_CREATED)
def create_participant(payload: ParticipantCreate, db: Session = Depends(get_db)) -> Participant:
    participant = Participant(study_id=payload.study_id, external_reference=payload.external_reference)
    db.add(participant)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="external_reference already exists") from exc
    db.refresh(participant)
    return participant
