from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.app.core.config import get_settings
from services.api.app.models.entities import (
    AssessmentSession,
    Operator,
    ParticipantStatus,
    Recording,
    TaskInstance,
)
from services.api.app.services.access import get_authorized_participant
from services.api.app.services.audit import add_audit_event
from services.api.app.services.media import MediaCleanupError


@dataclass(frozen=True, slots=True)
class PrivacyDeletionResult:
    participant_id: UUID
    deleted_session_count: int
    deleted_recording_count: int
    deleted_media_count: int
    participant_retained_as_withdrawn: bool


def _recording_path(recording: Recording) -> Path:
    prefix = "file://"
    if not recording.object_uri.startswith(prefix):
        raise MediaCleanupError("recording object URI is not a local contained object")
    root = get_settings().storage_root.resolve()
    path = Path(recording.object_uri[len(prefix) :]).resolve()
    if path == root or root not in path.parents:
        raise MediaCleanupError("recording object escapes the configured storage root")
    return path


def _quarantine_media(recordings: list[Recording]) -> list[tuple[Path, Path]]:
    moved: list[tuple[Path, Path]] = []
    try:
        for recording in recordings:
            original = _recording_path(recording)
            if not original.is_file():
                continue
            quarantine = original.with_name(f"{original.name}.deleting-{uuid4().hex}")
            original.replace(quarantine)
            moved.append((original, quarantine))
    except OSError as exc:
        _restore_quarantined(moved)
        raise MediaCleanupError("could not quarantine all participant media") from exc
    return moved


def _restore_quarantined(moved: list[tuple[Path, Path]]) -> None:
    failures: list[OSError] = []
    for original, quarantine in reversed(moved):
        try:
            if quarantine.exists():
                quarantine.replace(original)
        except OSError as exc:
            failures.append(exc)
    if failures:
        raise MediaCleanupError("database rollback succeeded but media restoration failed") from failures[0]


def _delete_quarantined(moved: list[tuple[Path, Path]]) -> int:
    deleted = 0
    failures: list[OSError] = []
    for _, quarantine in moved:
        try:
            quarantine.unlink(missing_ok=True)
            deleted += 1
        except OSError as exc:
            failures.append(exc)
    if failures:
        raise MediaCleanupError(
            "participant database data was removed but quarantined media cleanup is incomplete"
        ) from failures[0]
    return deleted


def remove_participant_data(
    db: Session,
    participant_id: UUID,
    operator: Operator,
    *,
    retain_withdrawn_marker: bool,
) -> PrivacyDeletionResult:
    participant = get_authorized_participant(
        db,
        participant_id,
        operator,
        for_update=True,
    )
    if participant is None:
        raise LookupError("participant not found")

    sessions = list(
        db.scalars(
            select(AssessmentSession).where(
                AssessmentSession.participant_id == participant.id
            )
        ).all()
    )
    session_ids = [item.id for item in sessions]
    recordings = (
        list(
            db.scalars(
                select(Recording)
                .join(TaskInstance, Recording.task_instance_id == TaskInstance.id)
                .where(TaskInstance.session_id.in_(session_ids))
            ).all()
        )
        if session_ids
        else []
    )
    moved = _quarantine_media(recordings)

    try:
        if retain_withdrawn_marker:
            for item in sessions:
                db.delete(item)
            participant.status = ParticipantStatus.WITHDRAWN.value
            participant.external_reference = None
            action = "participant.withdraw"
        else:
            db.delete(participant)
            action = "participant.delete"
        add_audit_event(
            db,
            operator,
            action=action,
            entity_type="participant",
            entity_id=participant_id,
            details={
                "deleted_session_count": len(sessions),
                "deleted_recording_count": len(recordings),
                "retained_withdrawn_marker": retain_withdrawn_marker,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        _restore_quarantined(moved)
        raise

    deleted_media_count = _delete_quarantined(moved)
    return PrivacyDeletionResult(
        participant_id=participant_id,
        deleted_session_count=len(sessions),
        deleted_recording_count=len(recordings),
        deleted_media_count=deleted_media_count,
        participant_retained_as_withdrawn=retain_withdrawn_marker,
    )
