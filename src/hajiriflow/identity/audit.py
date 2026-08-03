from collections.abc import Mapping, Sequence
from typing import Any

REDACTED = "[REDACTED]"
SENSITIVE_KEYS = frozenset(
    {
        "bank_account",
        "bank_number",
        "biometric",
        "biometric_template",
        "citizenship_number",
        "communication_secret",
        "device_password",
        "fingerprint",
        "fingerprint_data",
        "national_id",
        "pan_number",
        "password",
        "password_hash",
        "secret",
        "session_token",
        "token",
        "token_hash",
    }
)


def _normalise_key(key: object) -> str:
    return str(key).strip().lower().replace("-", "_")


def redact_audit_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): REDACTED
            if _normalise_key(key) in SENSITIVE_KEYS
            else redact_audit_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_audit_payload(item) for item in value]
    return value
