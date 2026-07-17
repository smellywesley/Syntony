from __future__ import annotations

from html import escape
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from services.api.app.core.security import require_api_key
from services.api.app.db.session import get_db
from services.api.app.models.entities import AssessmentSession, Event, Feature, TaskInstance
from services.api.app.schemas.api import (
    MeasurementSubmission,
    RepeatTaskRead,
    SessionCreate,
    SessionRead,
    SessionReport,
)
from services.api.app.services.measurement import schedule_repeat, session_metrics, submit_measurement
from services.api.app.services.sessions import create_session

router = APIRouter(prefix="/v1", tags=["sessions"], dependencies=[Depends(require_api_key)])


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
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="concurrent session creation conflict") from exc
    return _get_session(db, session.id)


@router.get("/sessions/{session_id}", response_model=SessionRead)
def read_session(session_id: UUID, db: Session = Depends(get_db)) -> AssessmentSession:
    return _get_session(db, session_id)


@router.post("/task-instances/{task_instance_id}/measure", status_code=status.HTTP_201_CREATED)
def measure_task(
    task_instance_id: UUID,
    payload: MeasurementSubmission,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    task = db.get(TaskInstance, task_instance_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task instance not found")
    try:
        recording = submit_measurement(db, task, payload)
    except (ValueError, RuntimeError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="task already has a recording from a concurrent submission") from exc
    return {"recording_id": str(recording.id), "status": "analyzed_synchronously"}


@router.post(
    "/task-instances/{task_instance_id}/repeat",
    response_model=RepeatTaskRead,
    status_code=status.HTTP_201_CREATED,
)
def create_repeat(
    task_instance_id: UUID,
    db: Session = Depends(get_db),
) -> RepeatTaskRead:
    task = db.get(TaskInstance, task_instance_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task instance not found")
    try:
        repeat = schedule_repeat(db, task)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="concurrent repeat creation conflict") from exc
    return RepeatTaskRead(task=repeat, reason="first capture accepted; optional repeat created")


@router.get("/sessions/{session_id}/report", response_model=SessionReport)
def session_report(session_id: UUID, db: Session = Depends(get_db)) -> SessionReport:
    session = _get_session(db, session_id)
    task_ids = [task.id for task in session.tasks]
    analyzed = sum(1 for task in session.tasks if task.status == "complete")
    feature_count = db.scalar(select(func.count(Feature.id)).where(Feature.task_instance_id.in_(task_ids))) if task_ids else 0
    event_count = db.scalar(select(func.count(Event.id)).where(Event.task_instance_id.in_(task_ids))) if task_ids else 0
    metrics, coupling = session_metrics(db, session.id)
    return SessionReport(
        session_id=session.id,
        status=session.status,
        task_count=len(task_ids),
        analyzed_task_count=analyzed,
        feature_count=int(feature_count or 0),
        event_count=int(event_count or 0),
        metrics=metrics,
        exploratory_coupling=coupling,
        note="Competition MVP measurement report only; coupling is exploratory and no diagnosis is generated.",
    )


@router.get("/sessions/{session_id}/visualization", response_class=HTMLResponse)
def session_visualization(session_id: UUID, db: Session = Depends(get_db)) -> HTMLResponse:
    session = _get_session(db, session_id)
    dual_task = db.scalar(
        select(TaskInstance).where(
            TaskInstance.session_id == session.id,
            TaskInstance.task_code == "T03",
            TaskInstance.repetition == 1,
        )
    )
    events = [] if dual_task is None else list(
        db.scalars(select(Event).where(Event.task_instance_id == dual_task.id).order_by(Event.start_ms)).all()
    )
    metrics, coupling = session_metrics(db, session.id)
    width = 900
    left_margin = 70
    plot_width = 780

    def x(timestamp: int) -> float:
        return left_margin + plot_width * min(10000, max(0, timestamp)) / 10000

    motor_marks = "".join(
        f'<circle cx="{x(event.start_ms):.1f}" cy="85" r="4" />'
        for event in events
        if event.modality == "motor"
    )
    speech_marks = "".join(
        f'<circle cx="{x(event.start_ms):.1f}" cy="160" r="4" />'
        for event in events
        if event.modality == "speech"
    )
    metric_html = "".join(
        f"<li><strong>{escape(name)}</strong>: {('unavailable' if value is None else f'{value:.2f}%')}</li>"
        for name, value in metrics.items()
    )
    coupling_value = coupling.get("event_coincidence_rate")
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>HandVoice synchronized measurement</title>
<style>body{{font-family:system-ui;max-width:1000px;margin:32px auto;padding:0 20px}}svg{{border:1px solid #bbb;width:100%;height:auto}}circle{{fill:currentColor}}.motor{{color:#222}}.speech{{color:#666}}code{{background:#eee;padding:2px 5px}}</style></head>
<body><h1>HandVoice synchronized measurement</h1>
<p>Session <code>{escape(str(session.id))}</code>. Coupling is exploratory.</p>
<svg viewBox="0 0 {width} 220" role="img" aria-label="Synchronized motor and speech events over ten seconds">
<line x1="{left_margin}" y1="85" x2="{left_margin + plot_width}" y2="85" stroke="currentColor" class="motor"/>
<line x1="{left_margin}" y1="160" x2="{left_margin + plot_width}" y2="160" stroke="currentColor" class="speech"/>
<text x="10" y="90">Hand</text><text x="10" y="165">DDK</text>
<g class="motor">{motor_marks}</g><g class="speech">{speech_marks}</g>
<text x="{left_margin}" y="205">0 s</text><text x="{left_margin + plot_width - 30}" y="205">10 s</text>
</svg>
<h2>Bidirectional dual-task cost</h2><ul>{metric_html}</ul>
<p><strong>Exploratory event coincidence rate:</strong> {('unavailable' if coupling_value is None else f'{coupling_value:.3f}')}</p>
</body></html>"""
    return HTMLResponse(html)
