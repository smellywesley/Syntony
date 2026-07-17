from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from services.api.app.db.session import get_db
from services.api.app.models.entities import AssessmentSession, Event, Feature, Recording, TaskInstance
from services.api.app.schemas.api import RecordingComplete, SessionCreate, SessionRead, SessionReport
from services.api.app.services.sessions import create_session

router = APIRouter(prefix="/v1", tags=["sessions"])


def _get_session(db: Session, session_id: UUID) -> AssessmentSession:
    session = db.scalar(
        select(AssessmentSession)
        .options(selectinload(AssessmentSession.tasks))
        .where(AssessmentSession.id == session_id)
    )
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session


@router.post("/sessions", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def create_session_route(payload: SessionCreate, db: Session = Depends(get_db)) -> AssessmentSession:
    try:
        session = create_session(db, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _get_session(db, session.id)


@router.get("/sessions/{session_id}", response_model=SessionRead)
def read_session(session_id: UUID, db: Session = Depends(get_db)) -> AssessmentSession:
    return _get_session(db, session_id)


@router.post("/task-instances/{task_instance_id}/complete", status_code=status.HTTP_201_CREATED)
def complete_task(task_instance_id: UUID, payload: RecordingComplete, db: Session = Depends(get_db)) -> dict[str, str]:
    task = db.get(TaskInstance, task_instance_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task instance not found")
    existing = db.scalar(select(Recording).where(Recording.task_instance_id == task.id, Recording.sha256 == payload.sha256.lower()))
    if existing is not None:
        return {"recording_id": str(existing.id), "status": "already_registered"}
    recording = Recording(
        task_instance_id=task.id,
        object_uri=payload.object_uri,
        sha256=payload.sha256.lower(),
        duration_ms=payload.duration_ms,
        video_fps=payload.video_fps,
        audio_sample_rate=payload.audio_sample_rate,
    )
    task.manifest_json = payload.manifest
    task.status = "captured"
    db.add(recording)
    db.commit()
    db.refresh(recording)
    return {"recording_id": str(recording.id), "status": "registered"}


@router.get("/sessions/{session_id}/report", response_model=SessionReport)
def session_report(session_id: UUID, db: Session = Depends(get_db)) -> SessionReport:
    session = _get_session(db, session_id)
    task_ids = [task.id for task in session.tasks]
    captured = db.scalar(select(func.count(Recording.id)).where(Recording.task_instance_id.in_(task_ids))) if task_ids else 0
    feature_count = db.scalar(select(func.count(Feature.id)).where(Feature.task_instance_id.in_(task_ids))) if task_ids else 0
    event_count = db.scalar(select(func.count(Event.id)).where(Event.task_instance_id.in_(task_ids))) if task_ids else 0
    return SessionReport(
        session_id=session.id,
        status=session.status,
        task_count=len(task_ids),
        captured_task_count=int(captured or 0),
        feature_count=int(feature_count or 0),
        event_count=int(event_count or 0),
        note="Measurement report only; no diagnosis is generated.",
    )
