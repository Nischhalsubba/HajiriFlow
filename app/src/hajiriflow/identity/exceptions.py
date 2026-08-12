class IdentityError(Exception):
    """Base identity-domain error."""


class InvalidCredentials(IdentityError):
    pass


class AuthenticationRateLimited(IdentityError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("too many authentication attempts")
        self.retry_after_seconds = retry_after_seconds


class InvalidSession(IdentityError):
    pass


class DuplicateUsername(IdentityError):
    pass


class InvalidAccountStatus(IdentityError):
    pass
