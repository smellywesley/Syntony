from __future__ import annotations

from html import escape
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.app.core.security import require_operator
from services.api.app.db.session import get_db
from services.api.app.models.entities import (
    AssessmentSession,
    Event,
    Feature,
    Operator,
    TaskInstance,
)
from services.api.app.schemas.api import (
    MeasurementRead,
    MeasurementSubmission,
    RepeatTaskRead,
    SessionCreate,
    SessionRead,
    SessionReport,
)
from services.api.app.services.measurement import schedule_repeat, session_metrics, submit_measurement
from services.api.app.services.media import MediaCleanupError, discard_pending_upload
from services.api.app.services.sessions import create_session
from services.api.app.services.access import (
    get_authorized_session,
    get_authorized_task,
    operator_owns_pending_upload,
    valid_pending_upload_key,
)
from services.api.app.services.audit import add_audit_event

router = APIRouter(prefix="/v1", tags=["sessions"])


def _privacy_cleanup_error(exc: MediaCleanupError) -> HTTPException:
    return HTTPException(
        status_code=500,
        detail={
            "code": "privacy_cleanup_failed",
            "guidance_key": "quality.error.privacy_cleanup_failed",
            "message": "The capture was not accepted, but its media could not be removed safely.",
        },
    )


def _get_session(
    db: Session,
    session_id: UUID,
    operator: Operator,
) -> AssessmentSession:
    session = get_authorized_session(db, session_id, operator)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session


@router.post("/sessions", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def create_session_route(
    payload: SessionCreate,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_operator),
) -> AssessmentSession:
    try:
        session = create_session(db, payload, operator)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="concurrent session creation conflict") from exc
    return _get_session(db, session.id, operator)


@router.get("/sessions/{session_id}", response_model=SessionRead)
def read_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_operator),
) -> AssessmentSession:
    return _get_session(db, session_id, operator)


@router.post(
    "/task-instances/{task_instance_id}/measure",
    response_model=MeasurementRead,
    status_code=status.HTTP_201_CREATED,
)
def measure_task(
    task_instance_id: UUID,
    payload: MeasurementSubmission,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_operator),
) -> MeasurementRead:
    if not valid_pending_upload_key(payload.storage_key):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="storage key is not a valid pending media object",
        )
    if not operator_owns_pending_upload(operator, payload.storage_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="media upload is not owned by the authenticated operator",
        )
    task = get_authorized_task(db, task_instance_id, operator)
    if task is None:
        try:
            discard_pending_upload(payload.storage_key)
        except MediaCleanupError as exc:
            raise _privacy_cleanup_error(exc) from exc
        except ValueError:
            # Never touch a non-pending object merely because the task ID is invalid.
            pass
        raise HTTPException(status_code=404, detail="task instance not found")
    try:
        outcome = submit_measurement(db, task, payload)
    except MediaCleanupError as exc:
        db.rollback()
        raise _privacy_cleanup_error(exc) from exc
    except (ValueError, RuntimeError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="task already has a recording from a concurrent submission") from exc
    assessment = outcome.assessment
    add_audit_event(
        db,
        operator,
        action="task.measure",
        entity_type="task_instance",
        entity_id=task.id,
        details={
            "quality_decision": assessment.decision.value,
            "accepted": outcome.recording is not None,
        },
    )
    db.commit()
    return MeasurementRead(
        recording_id=None if outcome.recording is None else outcome.recording.id,
        status=("analyzed_synchronously" if outcome.recording else "capture_not_accepted"),
        quality_decision=assessment.decision.value,
        reason_codes=[reason.value for reason in assessment.reason_codes],
        measured_quality=assessment.measured_quality,
        guidance_key=assessment.guidance_key,
    )


@router.post(
    "/task-instances/{task_instance_id}/repeat",
    response_model=RepeatTaskRead,
    status_code=status.HTTP_201_CREATED,
)
def create_repeat(
    task_instance_id: UUID,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_operator),
) -> RepeatTaskRead:
    task = get_authorized_task(db, task_instance_id, operator)
    if task is None:
        raise HTTPException(status_code=404, detail="task instance not found")
    try:
        repeat = schedule_repeat(db, task)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="concurrent repeat creation conflict") from exc
    add_audit_event(
        db,
        operator,
        action="task.repeat",
        entity_type="task_instance",
        entity_id=repeat.id,
        details={"source_task_instance_id": str(task.id)},
    )
    db.commit()
    return RepeatTaskRead(task=repeat, reason="first capture accepted; optional repeat created")


@router.get("/sessions/{session_id}/report", response_model=SessionReport)
def session_report(
    session_id: UUID,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_operator),
) -> SessionReport:
    session = _get_session(db, session_id, operator)
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
        note=(
            "Competition MVP measurement report only. Candidate speech onsets, speech dual-task costs, "
            "acoustic features and coupling are exploratory and unvalidated; no diagnosis is generated. "
            "The fixed task order supports within-session contrasts, not a causal interference claim."
        ),
    )


@router.get("/sessions/{session_id}/visualization", response_class=HTMLResponse)
def session_visualization(
    session_id: UUID,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_operator),
) -> HTMLResponse:
    session = _get_session(db, session_id, operator)
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
    motor_count = sum(event.modality == "motor" for event in events)
    speech_count = sum(event.modality == "speech" for event in events)
    event_rows = "".join(
        "<tr>"
        f"<td>{index}</td>"
        f"<td>{'Hand tap' if event.modality == 'motor' else 'Candidate acoustic onset (unvalidated)'}</td>"
        f"<td>{event.start_ms / 1000:.3f} seconds</td>"
        "</tr>"
        for index, event in enumerate(events, start=1)
    ) or '<tr><td colspan="3">No synchronized events were available.</td></tr>'
    metric_html = "".join(
        f"<li><strong>{escape(name)}</strong>: {('unavailable' if value is None else f'{value:.2f}%')}</li>"
        for name, value in metrics.items()
    )
    coupling_value = coupling.get("event_coincidence_rate")
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>HandVoice synchronized measurement</title>
<style>body{{font-family:system-ui;max-width:1000px;margin:32px auto;padding:0 20px;color:#111;background:#fff}}svg{{border:1px solid #777;width:100%;height:auto}}circle{{fill:currentColor}}.motor{{color:#111}}.speech{{color:#555}}code{{background:#eee;padding:2px 5px;overflow-wrap:anywhere}}table{{border-collapse:collapse;width:100%}}caption{{font-weight:700;text-align:left;margin-bottom:.5rem}}th,td{{border:1px solid #777;padding:.55rem;text-align:left}}th{{background:#eee}}</style></head>
<body><h1>HandVoice synchronized measurement</h1>
<p>Session <code>{escape(str(session.id))}</code>. Candidate speech onsets, speech dual-task costs and coupling are exploratory and unvalidated. The fixed task order supports within-session contrasts, not a causal interference claim.</p>
<p id="timeline-summary">The ten-second timeline contains {motor_count} hand-tapping events and {speech_count} candidate acoustic onsets. The same data is available in the event table after the chart.</p>
<svg viewBox="0 0 {width} 220" role="img" aria-label="Synchronized motor and speech events over ten seconds" aria-describedby="timeline-summary">
<line x1="{left_margin}" y1="85" x2="{left_margin + plot_width}" y2="85" stroke="currentColor" class="motor"/>
<line x1="{left_margin}" y1="160" x2="{left_margin + plot_width}" y2="160" stroke="currentColor" class="speech"/>
<text x="10" y="90">Hand</text><text x="10" y="165">DDK</text>
<g class="motor">{motor_marks}</g><g class="speech">{speech_marks}</g>
<text x="{left_margin}" y="205">0 s</text><text x="{left_margin + plot_width - 30}" y="205">10 s</text>
</svg>
<h2>Event timeline data</h2>
<table><caption>Events in timestamp order</caption><thead><tr><th scope="col">Event</th><th scope="col">Type</th><th scope="col">Time from task start</th></tr></thead><tbody>{event_rows}</tbody></table>
<h2>Fixed-order within-session dual-task contrasts</h2><ul>{metric_html}</ul>
<p><strong>Exploratory event coincidence rate:</strong> {('unavailable' if coupling_value is None else f'{coupling_value:.3f}')}</p>
</body></html>"""
    return HTMLResponse(html)
