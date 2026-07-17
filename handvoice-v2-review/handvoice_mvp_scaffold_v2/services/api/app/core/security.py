from __future__ import annotations

from hmac import compare_digest

from fastapi import Header, HTTPException, status

from services.api.app.core.config import get_settings


def require_api_key(x_handvoice_api_key: str | None = Header(default=None)) -> None:
    expected = get_settings().api_key
    if not x_handvoice_api_key or not compare_digest(x_handvoice_api_key, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key")
