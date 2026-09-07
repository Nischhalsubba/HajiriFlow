import json
import logging
import re
from collections.abc import Awaitable, Callable
from time import monotonic
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from hajiriflow.core.request_context import bind_request_id, reset_request_id

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")
REQUEST_LOGGER = logging.getLogger("hajiriflow.request")


def _request_id(request: Request) -> str:
    supplied = request.headers.get("X-Request-ID", "").strip()
    if REQUEST_ID_PATTERN.fullmatch(supplied):
        return supplied
    return uuid4().hex


def _route_path(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    return request.url.path


def _log_request(
    *,
    request: Request,
    request_id: str,
    status_code: int,
    duration_ms: int,
    exception_type: str | None = None,
) -> None:
    payload: dict[str, str | int] = {
        "duration_ms": duration_ms,
        "event": "http_request",
        "method": request.method,
        "path": _route_path(request),
        "request_id": request_id,
        "status_code": status_code,
    }
    if exception_type:
        payload["exception_type"] = exception_type
    message = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    if status_code >= 500:
        REQUEST_LOGGER.error(message)
    else:
        REQUEST_LOGGER.info(message)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Add request correlation without logging sensitive request contents."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = _request_id(request)
        request.state.request_id = request_id
        context_token = bind_request_id(request_id)
        started_at = monotonic()
        try:
            try:
                response = await call_next(request)
            except Exception as exc:
                _log_request(
                    request=request,
                    request_id=request_id,
                    status_code=500,
                    duration_ms=max(0, round((monotonic() - started_at) * 1000)),
                    exception_type=type(exc).__name__,
                )
                raise

            response.headers["X-Request-ID"] = request_id
            _log_request(
                request=request,
                request_id=request_id,
                status_code=response.status_code,
                duration_ms=max(0, round((monotonic() - started_at) * 1000)),
            )
            return response
        finally:
            reset_request_id(context_token)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, protected_environment: bool = False) -> None:
        super().__init__(app)
        self.protected_environment = protected_environment

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )

        # Workforce identity and future attendance/payroll payloads are private by
        # default. Prevent browsers, CDNs and intermediary caches from retaining
        # authenticated API responses unless a future endpoint opts into a more
        # specific cache policy intentionally.
        if request.url.path.startswith("/api/v1/"):
            response.headers.setdefault("Cache-Control", "no-store")
            response.headers.setdefault("Pragma", "no-cache")

        if self.protected_environment:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
            # Production API responses are data, not executable documents. This
            # also constrains any framework-generated error document.
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
            )

        return response
