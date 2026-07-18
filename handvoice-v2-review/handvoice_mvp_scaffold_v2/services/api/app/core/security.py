from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from services.api.app.db.session import get_db
from services.api.app.models.entities import Operator
from services.api.app.services.operators import resolve_operator


def _presented_key(
    x_handvoice_api_key: str | None,
    authorization: str | None,
) -> str | None:
    """Extract an operator key from either supported header.

    `Authorization: Bearer <key>` is preferred; the legacy
    `X-HandVoice-API-Key` header is still accepted for compatibility.
    """
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if x_handvoice_api_key:
        return x_handvoice_api_key.strip()
    return None


def require_operator(
    x_handvoice_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Operator:
    """Authenticate the caller against the operators table.

    Fails closed: an unknown, revoked, or missing key yields 401 and no
    operator exists when the table is empty, so the API is never open.
    """
    presented = _presented_key(x_handvoice_api_key, authorization)
    operator = resolve_operator(db, presented) if presented else None
    if operator is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing operator key",
        )
    return operator
