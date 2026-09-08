from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from hajiriflow.db.models.device import Device, RawPunch
from hajiriflow.db.models.workforce import CompanyProfile
from hajiriflow.db.session import get_session_factory
from hajiriflow.device_platform.adapters import (
    DeviceCapabilities,
    DeviceDiagnostics,
    PullBatch,
    PunchRecord,
)
from hajiriflow.device_platform.pull import DevicePullCoordinator, device_pull_lock

pytestmark = pytest.mark.usefixtures("database")


def _session():
    session = get_session_factory()()
    if session.get_bind().dialect.name != "postgresql":
        session.close()
        pytest.skip("PostgreSQL integration contract")
    return session


def _seed_device(session, *, code: str = "GATE-01") -> Device:
    organization = CompanyProfile(
        legal_name="HajiriFlow Test Organization",
        display_name="HajiriFlow Test",
    )
    session.add(organization)
    session.flush()
    device = Device(
        organization_id=organization.id,
        code=code,
        name=code,
        vendor="test-vendor",
        adapter_key="test-adapter",
        endpoint_uri="private://test-device",
        capabilities={"pull_punches": True},
    )
    session.add(device)
    session.flush()
    return device


class InvalidSecondPunchAdapter:
    adapter_key = "test-adapter"

    def capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities(pull_punches=True)

    def diagnostics(self) -> DeviceDiagnostics:
        return DeviceDiagnostics(reachable=True, observed_at=datetime.now(UTC))

    def pull_punches(self, *, cursor: str | None = None) -> PullBatch:
        del cursor
        observed_at = datetime.now(UTC)
        return PullBatch(
            punches=(
                PunchRecord(
                    device_user_identifier="101",
                    external_event_id="valid-first",
                    occurred_at=observed_at,
                    punch_kind="in",
                ),
                PunchRecord(
                    device_user_identifier="101",
                    external_event_id="invalid-second",
                    occurred_at=observed_at,
                    punch_kind="out",
                    evidence={"biometric_template": "must-never-be-stored"},
                ),
            ),
            next_cursor="cursor-that-must-not-advance",
        )

    def list_users(self):
        return ()


class CursorAdapter:
    adapter_key = "test-adapter"

    def __init__(self) -> None:
        self.cursors: list[str | None] = []

    def capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities(pull_punches=True)

    def diagnostics(self) -> DeviceDiagnostics:
        return DeviceDiagnostics(reachable=True, observed_at=datetime.now(UTC))

    def pull_punches(self, *, cursor: str | None = None) -> PullBatch:
        self.cursors.append(cursor)
        index = len(self.cursors)
        return PullBatch(
            punches=(
                PunchRecord(
                    device_user_identifier="101",
                    external_event_id=f"event-{index}",
                    occurred_at=datetime.now(UTC),
                    punch_kind="in" if index == 1 else "out",
                ),
            ),
            next_cursor=f"cursor-{index}",
        )

    def list_users(self):
        return ()


def test_postgresql_advisory_lock_excludes_overlapping_pull() -> None:
    first = _session()
    second = _session()
    device_id = uuid4()
    try:
        with device_pull_lock(first, device_id) as first_acquired:
            assert first_acquired is True
            with device_pull_lock(second, device_id) as second_acquired:
                assert second_acquired is False

        with device_pull_lock(second, device_id) as acquired_after_release:
            assert acquired_after_release is True
    finally:
        first.rollback()
        second.rollback()
        first.close()
        second.close()


def test_failed_pull_attempt_rolls_back_partial_punches() -> None:
    session = _session()
    try:
        device = _seed_device(session)
        pull = DevicePullCoordinator(session, max_attempts=2).pull_device(
            device=device,
            adapter=InvalidSecondPunchAdapter(),
        )
        session.commit()

        assert pull.status == "failed"
        assert pull.attempt_count == 2
        assert pull.ingested_count == 0
        assert pull.cursor_after is None
        assert pull.error_detail == "Device pull failed after bounded retries."
        assert session.scalar(select(func.count(RawPunch.id))) == 0
    finally:
        session.rollback()
        session.close()


def test_successive_pulls_resume_from_latest_successful_cursor() -> None:
    session = _session()
    try:
        device = _seed_device(session)
        adapter = CursorAdapter()
        coordinator = DevicePullCoordinator(session, max_attempts=1)

        first = coordinator.pull_device(device=device, adapter=adapter)
        second = coordinator.pull_device(device=device, adapter=adapter)
        session.commit()

        assert first.status == "succeeded"
        assert first.cursor_after == "cursor-1"
        assert second.status == "succeeded"
        assert second.cursor_before == "cursor-1"
        assert second.cursor_after == "cursor-2"
        assert adapter.cursors == [None, "cursor-1"]
        assert session.scalar(select(func.count(RawPunch.id))) == 2
    finally:
        session.rollback()
        session.close()
