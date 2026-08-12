import pytest
from pydantic import ValidationError

from hajiriflow.core.config import Settings


def test_rejects_short_session_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(session_secret="short")


def test_rejects_unknown_timezone() -> None:
    with pytest.raises(ValidationError):
        Settings(
            session_secret="a-valid-secret-that-is-longer-than-thirty-two-characters",
            timezone="Mars/Olympus_Mons",
        )
