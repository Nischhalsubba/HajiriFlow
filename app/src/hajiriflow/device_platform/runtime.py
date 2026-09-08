import json
import os
from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from hajiriflow.core.config import Settings
from hajiriflow.db.models.device import Device, DeviceCredential
from hajiriflow.device_platform.adapters import DeviceAdapter
from hajiriflow.device_platform.crypto import DeviceSecretCipher
from hajiriflow.device_platform.gateway_v1 import HajiriFlowGatewayV1Adapter


def device_secret_cipher_from_environment() -> DeviceSecretCipher:
    active_key_id = os.environ.get("HAJIRIFLOW_DEVICE_SECRET_ACTIVE_KEY_ID", "").strip()
    raw_keyring = os.environ.get("HAJIRIFLOW_DEVICE_SECRET_KEYS_JSON", "").strip()
    if not active_key_id or not raw_keyring:
        raise ValueError(
            "device secret keyring is not configured; set "
            "HAJIRIFLOW_DEVICE_SECRET_ACTIVE_KEY_ID and HAJIRIFLOW_DEVICE_SECRET_KEYS_JSON"
        )
    try:
        decoded = json.loads(raw_keyring)
    except json.JSONDecodeError as exc:
        raise ValueError("device secret keyring is not valid JSON") from exc
    if not isinstance(decoded, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in decoded.items()
    ):
        raise ValueError("device secret keyring must be a JSON object of string keys")
    return DeviceSecretCipher(active_key_id=active_key_id, keys=decoded)


def active_device_secret(
    session: Session,
    device: Device,
    *,
    cipher: DeviceSecretCipher,
) -> Mapping[str, str]:
    credential = session.scalar(
        select(DeviceCredential)
        .where(
            DeviceCredential.device_id == device.id,
            DeviceCredential.retired_at.is_(None),
        )
        .order_by(DeviceCredential.version.desc())
        .limit(1)
    )
    if credential is None:
        raise ValueError("device has no active encrypted credential")
    return cipher.decrypt(key_id=credential.key_id, ciphertext=credential.ciphertext)


def resolve_device_adapter(
    session: Session,
    device: Device,
    *,
    settings: Settings,
    cipher: DeviceSecretCipher | None = None,
) -> DeviceAdapter:
    if device.adapter_key != HajiriFlowGatewayV1Adapter.adapter_key:
        raise ValueError(f"unsupported device adapter: {device.adapter_key}")
    resolved_cipher = cipher or device_secret_cipher_from_environment()
    secret = active_device_secret(session, device, cipher=resolved_cipher)
    token = secret.get("token", "").strip()
    return HajiriFlowGatewayV1Adapter(
        endpoint_uri=device.endpoint_uri,
        token=token,
        timeout_seconds=10.0,
        allow_http=settings.environment in {"development", "test"},
    )
