import pytest

from hajiriflow.identity.audit import REDACTED, redact_audit_payload
from hajiriflow.identity.security import hash_password, verify_password


def test_password_hash_round_trip() -> None:
    password_hash = hash_password("correct-horse-battery-staple")
    assert password_hash != "correct-horse-battery-staple"
    assert verify_password("correct-horse-battery-staple", password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_short_password_is_rejected() -> None:
    with pytest.raises(ValueError):
        hash_password("too-short")


def test_audit_payload_redacts_nested_sensitive_fields() -> None:
    payload = {
        "username": "admin",
        "password_hash": "secret-hash",
        "nested": {"bank_number": "123", "safe": "visible"},
        "rows": [{"fingerprint_data": "template"}],
    }
    redacted = redact_audit_payload(payload)

    assert redacted["username"] == "admin"
    assert redacted["password_hash"] == REDACTED
    assert redacted["nested"]["bank_number"] == REDACTED
    assert redacted["nested"]["safe"] == "visible"
    assert redacted["rows"][0]["fingerprint_data"] == REDACTED
