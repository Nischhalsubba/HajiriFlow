import json
from collections.abc import Mapping

from cryptography.fernet import Fernet, InvalidToken


class DeviceSecretCipher:
    """Encrypts device secrets with externally managed, versioned Fernet keys."""

    def __init__(self, *, active_key_id: str, keys: Mapping[str, str | bytes]) -> None:
        if active_key_id not in keys:
            raise ValueError("active device-secret key is not present in the keyring")
        self.active_key_id = active_key_id
        self._keys = {
            key_id: Fernet(value.encode() if isinstance(value, str) else value)
            for key_id, value in keys.items()
        }

    def encrypt(self, secret: Mapping[str, str]) -> tuple[str, bytes]:
        if not secret:
            raise ValueError("device credential payload must not be empty")
        encoded = json.dumps(
            dict(secret),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return self.active_key_id, self._keys[self.active_key_id].encrypt(encoded)

    def decrypt(self, *, key_id: str, ciphertext: bytes) -> dict[str, str]:
        cipher = self._keys.get(key_id)
        if cipher is None:
            raise ValueError("unknown device-secret key identifier")
        try:
            decoded = cipher.decrypt(ciphertext)
        except InvalidToken as exc:
            raise ValueError("device credential ciphertext could not be decrypted") from exc
        payload = json.loads(decoded)
        if not isinstance(payload, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in payload.items()
        ):
            raise ValueError("device credential ciphertext contains an invalid payload")
        return payload
