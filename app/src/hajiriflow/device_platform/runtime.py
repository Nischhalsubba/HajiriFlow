from sqlalchemy import select
from sqlalchemy.orm import Session

from hajiriflow.core.config import Settings
from hajiriflow.db.models.device import Device, DeviceCredential
from hajiriflow.db.models.device_baseline import DeviceRuntimeConfiguration
from hajiriflow.device_platform.adapters import DeviceAdapter
from hajiriflow.device_platform.crypto import DeviceSecretCipher
from hajiriflow.device_platform.gateway_adapter import HajiriFlowGatewayAdapter


def build_device_secret_cipher(settings: Settings) -> DeviceSecretCipher:
    keys = settings.device_secret_keys
    if not settings.device_secret_active_key_id or not keys:
        raise ValueError(
            "device-secret encryption is not configured; set the active key id and keyring"
        )
    return DeviceSecretCipher(
        active_key_id=settings.device_secret_active_key_id,
        keys=keys,
    )


def _active_credential(session: Session, device: Device) -> DeviceCredential | None:
    return session.scalar(
        select(DeviceCredential)
        .where(
            DeviceCredential.device_id == device.id,
            DeviceCredential.retired_at.is_(None),
        )
        .order_by(DeviceCredential.version.desc())
        .limit(1)
    )


def resolve_registered_adapter(
    *,
    session: Session,
    settings: Settings,
    device: Device,
) -> DeviceAdapter | None:
    """Resolve only explicitly supported adapter keys; unknown hardware fails closed."""

    if device.adapter_key != HajiriFlowGatewayAdapter.adapter_key:
        return None

    runtime = session.get(DeviceRuntimeConfiguration, device.id)
    timeout_seconds = runtime.timeout_seconds if runtime else 10
    credential = _active_credential(session, device)
    secret: dict[str, str] = {}
    if credential is not None:
        cipher = build_device_secret_cipher(settings)
        secret = cipher.decrypt(key_id=credential.key_id, ciphertext=credential.ciphertext)

    unsupported = set(secret) - {"bearer_token"}
    if unsupported:
        raise ValueError("gateway credential contains unsupported fields")
    return HajiriFlowGatewayAdapter(
        endpoint_uri=device.endpoint_uri,
        timeout_seconds=timeout_seconds,
        bearer_token=secret.get("bearer_token"),
    )
