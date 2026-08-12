from collections.abc import Generator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from hajiriflow.core.config import Settings, get_settings
from hajiriflow.db.session import get_session_factory
from hajiriflow.identity.exceptions import InvalidSession
from hajiriflow.identity.permissions import has_permission
from hajiriflow.identity.service import IdentityService, SessionPrincipal
from hajiriflow.identity.tokens import verify_csrf_token


@dataclass(frozen=True, slots=True)
class RequestIdentity:
    principal: SessionPrincipal
    raw_token: str


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_raw_session_token(request: Request, settings: Settings) -> str | None:
    authorization = request.headers.get("authorization", "")
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() == "bearer" and value:
        return value.strip()
    return request.cookies.get(settings.session_cookie_name)


def current_identity(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RequestIdentity:
    raw_token = get_raw_session_token(request, settings)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    try:
        principal = IdentityService(session, settings).resolve_session(raw_token)
    except InvalidSession as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="session is invalid or expired",
        ) from exc
    return RequestIdentity(principal=principal, raw_token=raw_token)


def require_permission(permission: str):
    def dependency(
        identity: Annotated[RequestIdentity, Depends(current_identity)],
        organization_id: UUID | None = None,
    ) -> RequestIdentity:
        if not has_permission(
            identity.principal.grants,
            permission,
            organization_id=organization_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="permission denied",
            )
        return identity

    return dependency


def require_csrf(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    header_token = request.headers.get("x-csrf-token")
    if (
        not cookie_token
        or not header_token
        or cookie_token != header_token
        or not verify_csrf_token(header_token, settings.session_secret)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed",
        )
