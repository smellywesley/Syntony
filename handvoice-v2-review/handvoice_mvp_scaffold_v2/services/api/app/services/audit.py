from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from services.api.app.models.entities import AuditEvent, Operator


def add_audit_event(
    db: Session,
    operator: Operator,
    *,
    action: str,
    entity_type: str,
    entity_id: object,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    """Stage a privacy-safe audit event in the caller's transaction."""
    event = AuditEvent(
        actor=f"operator:{operator.id}",
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        details_json={
            "operator_label": operator.label,
            "operator_study_id": operator.study_id,
            **(details or {}),
        },
    )
    db.add(event)
    return event
