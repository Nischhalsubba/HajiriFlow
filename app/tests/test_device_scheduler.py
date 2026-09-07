from datetime import UTC, datetime

import pytest

from hajiriflow.db.models.device import Device
from hajiriflow.db.models.workforce import CompanyProfile
from hajiriflow.db.session import get_session_factory
from hajiriflow.device_platform.adapters import (
    DeviceCapabilities,
    DeviceDiagnostics,
    PullBatch,
)
from hajiriflow.worker.scheduler import DevicePullScheduler

pytestmark = pytest.mark.usefixtures("database")


class EmptyAdapter:
    adapter_key = "test"

    def capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities(pull_punches=True)

    def diagnostics(self) -> DeviceDiagnostics:
        return DeviceDiagnostics(reachable=True, observed_at=datetime.now(UTC))

    def pull_punches(self, *, cursor: str | None = None) -> PullBatch:
        return PullBatch(punches=(), next_cursor=cursor)

    def list_users(self) -> tuple:
        return ()


def _device(session) -> Device:
    organization = CompanyProfile(legal_name="Scheduler Org", display_name="Scheduler Org")
    session.add(organization)
    session.flush()
    device = Device(
        organization_id=organization.id,
        code="gate",
        name="Gate device",
        vendor="test",
        adapter_key="test",
        endpoint_uri="test://gate",
        capabilities={"pull_punches": True},
        pull_interval_seconds=60,
    )
    session.add(device)
    session.flush()
    return device


def test_scheduler_respects_per_device_pull_interval() -> None:
    session = get_session_factory()()
    try:
        _device(session)
        observed = datetime(2026, 9, 7, 8, 0, tzinfo=UTC)
        scheduler = DevicePullScheduler(session, adapter_resolver=lambda _device: None)

        first = scheduler.run_once(now=observed)
        assert len(first) == 1
        assert first[0].status == "skipped"
        assert first[0].error_code == "adapter_unavailable"

        assert scheduler.run_once(now=observed.replace(second=30)) == ()
        later = observed.replace(minute=1, second=1)
        assert len(scheduler.run_once(now=later)) == 1
    finally:
        session.close()


def test_scheduler_runs_supported_adapter_through_pull_coordinator() -> None:
    session = get_session_factory()()
    try:
        device = _device(session)
        scheduler = DevicePullScheduler(
            session,
            adapter_resolver=lambda candidate: EmptyAdapter() if candidate.id == device.id else None,
        )

        result = scheduler.run_once()
        assert len(result) == 1
        assert result[0].status == "succeeded"
        assert result[0].ingested_count == 0
        assert device.last_seen_at is not None
    finally:
        session.close()


def test_adapter_resolution_error_does_not_log_exception_message(caplog) -> None:
    session = get_session_factory()()
    try:
        _device(session)

        def unsafe_resolver(_device):
            raise RuntimeError("password=must-not-appear")

        scheduler = DevicePullScheduler(session, adapter_resolver=unsafe_resolver)
        result = scheduler.run_once()

        assert result[0].status == "skipped"
        assert "RuntimeError" in caplog.text
        assert "must-not-appear" not in caplog.text
    finally:
        session.close()
