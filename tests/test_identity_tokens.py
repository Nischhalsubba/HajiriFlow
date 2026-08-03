import pytest
from pydantic import ValidationError

from hajiriflow.core.config import Settings
from hajiriflow.identity.tokens import generate_csrf_token, verify_csrf_token


def test_csrf_tokens_are_signed_and_tamper_evident() -> None:
    secret = "a-valid-secret-that-is-longer-than-thirty-two-characters"
    token = generate_csrf_token(secret)
    assert verify_csrf_token(token, secret)
    assert not verify_csrf_token(f"{token}x", secret)


def test_production_requires_secure_cookies() -> None:
    with pytest.raises(ValidationError):
        Settings(
            session_secret="a-valid-secret-that-is-longer-than-thirty-two-characters",
            environment="production",
            cookie_secure=False,
        )
