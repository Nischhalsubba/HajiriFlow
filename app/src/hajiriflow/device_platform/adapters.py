from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class DeviceCapabilities:
    pull_punches: bool = True
    historical_pulls: bool = False
    list_users: bool = False
    push_users: bool = False
    biometric_templates: bool = False
    archive_users: bool = False
    restore_users: bool = False
    realtime_events: bool = False


@dataclass(frozen=True, slots=True)
class DeviceDiagnostics:
    reachable: bool
    observed_at: datetime
    firmware_version: str | None = None
    device_time: datetime | None = None
    message: str | None = None
    metadata: dict[str, str | int | bool | None] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PunchRecord:
    device_user_identifier: str
    occurred_at: datetime
    external_event_id: str | None = None
    punch_kind: str = "unknown"
    verification_method: str | None = None
    evidence: dict[str, str | int | float | bool | None] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DeviceUserRecord:
    external_user_id: str
    display_name: str | None = None
    privilege: str | None = None
    active: bool = True
    template_count: int = 0
    metadata: dict[str, str | int | bool | None] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DeviceIdentityBundle:
    external_user_id: str
    display_name: str | None = None
    privilege: str | None = None
    active: bool = True
    template_count: int = 0
    metadata: dict[str, str | int | bool | None] = field(default_factory=dict)
    biometric_payload: str | None = None


@dataclass(frozen=True, slots=True)
class DeviceWriteResult:
    accepted: bool
    code: str
    message: str | None = None


@dataclass(frozen=True, slots=True)
class PullBatch:
    punches: tuple[PunchRecord, ...]
    next_cursor: str | None = None


@runtime_checkable
class DeviceAdapter(Protocol):
    """Vendor-neutral boundary implemented by each supported device family."""

    adapter_key: str

    def capabilities(self) -> DeviceCapabilities: ...

    def diagnostics(self) -> DeviceDiagnostics: ...

    def pull_punches(self, *, cursor: str | None = None) -> PullBatch: ...

    def list_users(self) -> tuple[DeviceUserRecord, ...]: ...
