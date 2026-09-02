from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from hajiriflow.api.dependencies import (
    RequestIdentity,
    current_identity,
    get_db,
    require_csrf,
    require_permission,
)
from hajiriflow.core.config import Settings, get_settings
from hajiriflow.identity.exceptions import (
    AuthenticationRateLimited,
    DuplicateUsername,
    InvalidAccountStatus,
    InvalidCredentials,
)
from hajiriflow.identity.permissions import FULL_ACCESS, ScopeType, has_permission
from hajiriflow.identity.service import IdentityService
from hajiriflow.identity.tokens import generate_csrf_token

router = APIRouter(prefix="/api/v1", tags=["identity"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=1, max_length=500)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=500)
    new_password: str = Field(min_length=12, max_length=500)


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=12, max_length=500)
    must_change_password: bool = True


class UserStatusRequest(BaseModel):
    status: Literal["active", "disabled"]


class AssignRoleRequest(BaseModel):
    role_code: str = Field(min_length=1, max_length=100)
    scope_type: ScopeType = ScopeType.GLOBAL
    scope_id: UUID | None = None


class UserView(BaseModel):
    id: UUID
    username: str
    display_name: str
    status: str
    must_change_password: bool
    employee_id: UUID | None
    created_at: datetime


class PermissionView(BaseModel):
    code: str
    scope_type: ScopeType
    scope_id: UUID | None


class SessionView(BaseModel):
    user: UserView
    expires_at: datetime
    permissions: list[PermissionView]
    csrf_token: str | None = None


def user_view(user) -> UserView:
    return UserView(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        status=user.status,
        must_change_password=user.must_change_password,
        employee_id=user.employee_id,
        created_at=user.created_at,
    )


def set_auth_cookies(
    response: Response,
    *,
    raw_token: str,
    csrf_token: str,
    settings: Settings,
) -> None:
    max_age = settings.session_ttl_minutes * 60
    response.set_cookie(
        settings.session_cookie_name,
        raw_token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_same_site,
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_same_site,
        path="/",
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")


@router.post("/auth/login", response_model=SessionView)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionView:
    service = IdentityService(session, settings)
    try:
        created = service.authenticate(
            username=payload.username,
            password=payload.password,
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except AuthenticationRateLimited as exc:
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many login attempts",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except (InvalidCredentials, ValueError) as exc:
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid username or password",
        ) from exc

    csrf_token = generate_csrf_token(settings.session_secret)
    set_auth_cookies(
        response,
        raw_token=created.token,
        csrf_token=csrf_token,
        settings=settings,
    )
    grants = service.grants_for_user(created.user.id)
    return SessionView(
        user=user_view(created.user),
        expires_at=created.session.expires_at,
        permissions=[
            PermissionView(
                code=grant.permission,
                scope_type=grant.scope_type,
                scope_id=grant.scope_id,
            )
            for grant in sorted(grants, key=lambda item: item.permission)
        ],
        csrf_token=csrf_token,
    )


@router.get("/auth/me", response_model=SessionView)
def me(identity: Annotated[RequestIdentity, Depends(current_identity)]) -> SessionView:
    principal = identity.principal
    return SessionView(
        user=user_view(principal.user),
        expires_at=principal.session.expires_at,
        permissions=[
            PermissionView(
                code=grant.permission,
                scope_type=grant.scope_type,
                scope_id=grant.scope_id,
            )
            for grant in sorted(principal.grants, key=lambda item: item.permission)
        ],
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[RequestIdentity, Depends(current_identity)],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    IdentityService(session, settings).revoke_session(
        identity.principal.session.id,
        identity.principal.user.id,
    )
    clear_auth_cookies(response, settings)


@router.post("/auth/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[RequestIdentity, Depends(current_identity)],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    service = IdentityService(session, settings)
    try:
        service.change_password(
            user=identity.principal.user,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except (InvalidCredentials, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc) or "password change failed",
        ) from exc
    clear_auth_cookies(response, settings)


@router.get("/admin/users", response_model=list[UserView])
def list_users(
    _: Annotated[
        RequestIdentity, Depends(require_permission("identity.user.read"))
    ],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[UserView]:
    users = IdentityService(session, settings).list_users()
    return [user_view(user) for user in users]


@router.post("/admin/users", response_model=UserView, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: CreateUserRequest,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity, Depends(require_permission("identity.user.create"))
    ],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserView:
    try:
        user = IdentityService(session, settings).create_user(
            username=payload.username,
            display_name=payload.display_name,
            password=payload.password,
            must_change_password=payload.must_change_password,
            actor_user_id=identity.principal.user.id,
        )
    except (DuplicateUsername, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="username already exists" if isinstance(exc, DuplicateUsername) else str(exc),
        ) from exc
    return user_view(user)


@router.patch("/admin/users/{user_id}/status", response_model=UserView)
def set_user_status(
    user_id: UUID,
    payload: UserStatusRequest,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity, Depends(require_permission("identity.user.manage"))
    ],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserView:
    if user_id == identity.principal.user.id and payload.status == "disabled":
        raise HTTPException(status_code=400, detail="you cannot disable your own account")
    try:
        user = IdentityService(session, settings).set_user_status(
            user_id=user_id,
            status=payload.status,
            actor_user_id=identity.principal.user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="user not found") from exc
    except InvalidAccountStatus as exc:
        raise HTTPException(status_code=400, detail="invalid account status") from exc
    return user_view(user)


@router.post("/admin/users/{user_id}/roles", status_code=status.HTTP_201_CREATED)
def assign_role(
    user_id: UUID,
    payload: AssignRoleRequest,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity, Depends(require_permission("identity.role.assign"))
    ],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    if payload.role_code == "system_administrator" and not has_permission(
        identity.principal.grants,
        FULL_ACCESS,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="system administrator role requires system administrator access",
        )
    try:
        assignment = IdentityService(session, settings).assign_role(
            user_id=user_id,
            role_code=payload.role_code,
            actor_user_id=identity.principal.user.id,
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"assignment_id": str(assignment.id)}
