from __future__ import annotations

from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.app.models.entities import Operator


def hash_key(raw_key: str) -> str:
    """Return the storage hash for an operator key.

    Operator keys are high-entropy secrets (not user passwords), so a single
    SHA-256 is an appropriate, fast lookup key. Only the hash is ever stored.
    """
    return sha256(raw_key.encode("utf-8")).hexdigest()


def resolve_operator(db: Session, raw_key: str) -> Operator | None:
    """Look up an active operator by presented key, or None if unknown/revoked."""
    if not raw_key:
        return None
    operator = db.scalar(select(Operator).where(Operator.key_hash == hash_key(raw_key)))
    if operator is None or not operator.active:
        return None
    return operator


def create_operator(
    db: Session,
    *,
    label: str,
    raw_key: str,
    study_id: str | None = None,
) -> Operator:
    operator = Operator(label=label, study_id=study_id, key_hash=hash_key(raw_key))
    db.add(operator)
    db.commit()
    db.refresh(operator)
    return operator


def seed_bootstrap_operator(db: Session, raw_key: str) -> Operator | None:
    """Idempotently create the first operator from a bootstrap key.

    Returns the operator if one was created, or None if a matching active
    operator already exists (so restarts do not create duplicates).
    """
    if not raw_key:
        return None
    if resolve_operator(db, raw_key) is not None:
        return None
    return create_operator(db, label="bootstrap", raw_key=raw_key, study_id=None)
