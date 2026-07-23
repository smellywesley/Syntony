"""Unit tests for DB-backed operator authentication that replaces the single
global API key: key hashing, idempotent bootstrap seeding, and resolution of
active, unknown, and revoked keys."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from services.api.app.db.base import Base
from services.api.app.models.entities import Operator
from services.api.app.services.operators import (
    create_operator,
    hash_key,
    resolve_demo_operator,
    resolve_operator,
    seed_bootstrap_operator,
)


def _fresh_db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_hash_key_is_stable_and_not_plaintext():
    hashed = hash_key("super-secret")
    assert hashed == hash_key("super-secret")
    assert len(hashed) == 64
    assert "super-secret" not in hashed


def test_seed_bootstrap_operator_is_idempotent():
    with _fresh_db() as db:
        first = seed_bootstrap_operator(db, "bootstrap-key")
        assert first is not None
        second = seed_bootstrap_operator(db, "bootstrap-key")
        assert second is None
        operators = db.scalars(select(Operator)).all()
        assert len(operators) == 1


def test_seed_bootstrap_operator_ignores_empty_key():
    with _fresh_db() as db:
        assert seed_bootstrap_operator(db, "") is None
        assert db.scalars(select(Operator)).all() == []


def test_resolve_operator_active_unknown_and_revoked():
    with _fresh_db() as db:
        operator = create_operator(db, label="site-a", raw_key="site-a-key", study_id="HV-1")

        resolved = resolve_operator(db, "site-a-key")
        assert resolved is not None and resolved.id == operator.id

        assert resolve_operator(db, "wrong-key") is None
        assert resolve_operator(db, "") is None

        operator.active = False
        db.commit()
        assert resolve_operator(db, "site-a-key") is None


def test_resolve_demo_operator_only_returns_active_bootstrap_operator():
    with _fresh_db() as db:
        create_operator(db, label="site-a", raw_key="site-a-key")
        bootstrap = create_operator(db, label="bootstrap", raw_key="demo-key")
        assert resolve_demo_operator(db).id == bootstrap.id
        bootstrap.active = False
        db.commit()
        assert resolve_demo_operator(db) is None
