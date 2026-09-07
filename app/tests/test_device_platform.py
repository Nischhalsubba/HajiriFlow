from datetime import UTC, date, datetime

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import func, select

from hajiriflow.db.models.device import Device, DeviceCredential, RawPunch
from hajiriflow.db.models.workforce import CompanyProfile
from hajiriflow.db.session import get_session_factory
from hajiriflow.device_platform.adapters import (
    DeviceCapabilities,
    DeviceDiagnostics,
    PullBatch,
    PunchRecord,
)
from hajiriflow.device_platform.crypto import DeviceSecretCipher
from hajiriflow.device_platform.pull import DevicePullCoordinator
from hajiriflow.device_platform.service import DevicePlatformService


def _organization(session, name: str = "Acme") -> CompanyProfile:
    organization = CompanyProfile(legal_name=name, display_name=name)
    session.add(organization)
    session.flush()
    return organization


def _device(session, organization: CompanyProfile, code: str) -> Device:
    device = Device(
        organization_id=organization.id,
        code=code,
        name=f"Device {code}",
        vendor="test-vendor",
        model="virtual",
        serial_number=f"serial-{code}",
        adapter_key="test",
        endpoint_uri=f"test://{code}",
        capabilities={"pull_punches": True},
    )
    session.add(device)
    session.flush()
    return device


class WorkingAdapter:
    adapter_key = "test"

    def __init__(self, event_id: str) -> None:
        self.event_id = event_id

    def capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities()

    def diagnostics(self) -> DeviceDiagnostics:
        return DeviceDiagnostics(reachable=True, observed_at=datetime.now(UTC))

    def pull_punches(self, *, cursor: str | None = None) -> PullBatch:
        del cursor
        return PullBatch(
            punches=(
                PunchRecord(
                    external_event_id=self.event_id,
                    device_user_identifier="42",
                    occurred_at=datetime(2026, 9, 7, 8, 30, tzinfo=UTC),
                    punch_kind="in",
                    verification_method="fingerprint",
                    evidence={"sequence": 1},
                ),
            ),
            next_cursor="next",
        )

    def list_users(self):
        return ()


class FailingAdapter(WorkingAdapter):
    def pull_punches(self, *, cursor: str | None = None) -> PullBatch:
        del cursor
        raise ConnectionError("simulated device failure")


def test_device_credentials_are_encrypted_and_rotatable(database) -> None:
    del database
    session = get_session_factory()()
    try:
        organization = _organization(session)
        device = _device(session, organization, "front-gate")
        key = Fernet.generate_key()
        cipher = DeviceSecretCipher(active_key_id="k1", keys={"k1": key})
        service = DevicePlatformService(session)

        first = service.rotate_credential(
            device=device,
            secret={"username": "admin", "password": "not-stored-in-plain-text"},
            cipher=cipher,
            actor_user_id=None,
        )
        second = service.rotate_credential(
            device=device,
            secret={"username": "admin", "password": "rotated-secret"},
            cipher=cipher,
            actor_user_id=None,
        )
        session.flush()

        assert b"rotated-secret" not in second.ciphertext
        assert cipher.decrypt(key_id=second.key_id, ciphertext=second.ciphertext) == {
            "password": "rotated-secret",
            "username": "admin",
        }
        assert first.retired_at is not None
        assert second.version == 2
        assert session.scalar(select(func.count(DeviceCredential.id))) == 2
    finally:
        session.close()


def test_repeating_pull_is_idempotent(database) -> None:
    del database
    session = get_session_factory()()
    try:
        organization = _organization(session)
        device = _device(session, organization, "gate-a")
        coordinator = DevicePullCoordinator(session, max_attempts=2)
        adapter = WorkingAdapter("event-1")

        first = coordinator.pull_device(device=device, adapter=adapter)
        second = coordinator.pull_device(device=device, adapter=adapter)

        assert first.status == "succeeded"
        assert first.ingested_count == 1
        assert second.status == "succeeded"
        assert second.ingested_count == 0
        assert second.duplicate_count == 1
        assert session.scalar(select(func.count(RawPunch.id))) == 1
    finally:
        session.close()


def test_one_failing_device_does_not_block_another(database) -> None:
    del database
    session = get_session_factory()()
    try:
        organization = _organization(session)
        broken = _device(session, organization, "broken")
        healthy = _device(session, organization, "healthy")
        coordinator = DevicePullCoordinator(session, max_attempts=2)

        results = coordinator.pull_many(
            (
                (broken, FailingAdapter("unused")),
                (healthy, WorkingAdapter("healthy-event")),
            )
        )

        assert [result.status for result in results] == ["failed", "succeeded"]
        assert session.scalar(select(func.count(RawPunch.id))) == 1
    finally:
        session.close()


def test_raw_punch_evidence_rejects_sensitive_payloads(database) -> None:
    del database
    session = get_session_factory()()
    try:
        organization = _organization(session)
        device = _device(session, organization, "gate-b")
        service = DevicePlatformService(session)
        punch = PunchRecord(
            device_user_identifier="42",
            occurred_at=datetime(2026, 9, 7, 8, 30, tzinfo=UTC),
            verification_method="fingerprint",
            evidence={"fingerprint_template": "must-never-be-stored"},
        )

        with pytest.raises(ValueError, match="sensitive device evidence"):
            service.ingest_punches(device=device, punches=(punch,))
    finally:
        session.close()


def test_raw_punch_rows_are_immutable(database) -> None:
    del database
    session = get_session_factory()()
    try:
        organization = _organization(session)
        device = _device(session, organization, "gate-c")
        service = DevicePlatformService(session)
        service.ingest_punches(
            device=device,
            punches=(
                PunchRecord(
                    device_user_identifier="42",
                    occurred_at=datetime(2026, 9, 7, 8, 30, tzinfo=UTC),
                    evidence={"sequence": 3},
                ),
            ),
        )
        punch = session.scalar(select(RawPunch))
        assert punch is not None
        punch.punch_kind = "out"
        with pytest.raises(RuntimeError, match="immutable"):
            session.flush()
        session.rollback()
    finally:
        session.close()
