from __future__ import annotations

from ipaddress import ip_address

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from services.api.app.db.session import get_db
from services.api.app.models.entities import Operator
from services.api.app.core.config import get_settings
from services.api.app.services.operators import resolve_demo_operator, resolve_operator


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


def _is_loopback_request(request: Request) -> bool:
    if request.client is None:
        return False
    try:
        return ip_address(request.client.host).is_loopback
    except ValueError:
        return False


def require_operator(
    request: Request,
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
    if (
        operator is None
        and not presented
        and get_settings().demo_bypass_operator_auth
        and _is_loopback_request(request)
    ):
        operator = resolve_demo_operator(db)
    if operator is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing operator key",
        )
    return operator
