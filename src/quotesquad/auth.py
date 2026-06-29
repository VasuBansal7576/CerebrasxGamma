from __future__ import annotations

from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from quotesquad.config import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]


def require_api_key(request: Request, settings: SettingsDep) -> None:
    secret = settings.api_key
    if secret is None or secret.get_secret_value() == "":
        return
    supplied = request.headers.get("x-quotesquad-key", "")
    if not compare_digest(supplied, secret.get_secret_value()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
