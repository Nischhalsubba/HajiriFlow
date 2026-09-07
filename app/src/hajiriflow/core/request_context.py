from contextvars import ContextVar, Token

_REQUEST_ID: ContextVar[str | None] = ContextVar("hajiriflow_request_id", default=None)


def bind_request_id(request_id: str) -> Token[str | None]:
    return _REQUEST_ID.set(request_id)


def current_request_id() -> str | None:
    return _REQUEST_ID.get()


def reset_request_id(token: Token[str | None]) -> None:
    _REQUEST_ID.reset(token)
