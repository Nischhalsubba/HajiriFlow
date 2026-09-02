from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from hajiriflow.api.dependencies import RequestIdentity, current_identity
from hajiriflow.core.config import Settings, get_settings
from hajiriflow.identity.tokens import generate_csrf_token, verify_csrf_token

router = APIRouter(prefix="/api/v1", tags=["identity"])


def set_csrf_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        settings.csrf_cookie_name,
        token,
        max_age=settings.session_ttl_minutes * 60,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_same_site,
        path="/",
    )


@router.get("/auth/csrf")
def csrf_token(
    request: Request,
    response: Response,
    _: Annotated[RequestIdentity, Depends(current_identity)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    token = request.cookies.get(settings.csrf_cookie_name)
    if not token or not verify_csrf_token(token, settings.session_secret):
        token = generate_csrf_token(settings.session_secret)
        set_csrf_cookie(response, token, settings)
    return {"csrf_token": token}
