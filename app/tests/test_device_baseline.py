import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from hajiriflow.core.config import Settings, get_settings
from hajiriflow.db.models.device import Device, DevicePullSession, RawPunch
from hajiriflow.db.models.device_baseline import DeviceOperation
from hajiriflow.db.models.workforce import CompanyProfile
from hajiriflow.db.session import get_session_factory
from hajiriflow.device_platform.adapters import (
    DeviceCapabilities,
    DeviceDiagnostics,
    DeviceUserRecord,
    PullBatch,
    PunchRecord,
)
from hajiriflow.device_platform.gateway_adapter import HajiriFlowGatewayAdapter
from hajiriflow.device_platform.operations import DeviceOperationService
from hajiriflow.device_platform.runtime import (
    build_device_secret_cipher,
    resolve_registered_adapter,
)
from hajiriflow.device_platform.service import DevicePlatformService
from hajiriflow.identity.bootstrap import seed_identity_catalog
from hajiriflow.identity.permissions import ScopeType
from hajiriflow.identity.service import IdentityService
from hajiriflow.main import create_app

pytestmark = pytest.mark.usefixtures("database")


def _organization(session, name: str = "Device Baseline") -> CompanyProfile:
    organization = CompanyProfile(legal_name=name, display_name=name)
    session.add(organization)
    session.flush()
    return organization


def _device(session, organization: CompanyProfile, code: str = "GATE-1") -> Device:
    device = Device(
        organization_id=organization.id,
        code=code,
        name="Main Gate",
        vendor="Gateway",
        adapter_key="hajiriflow_gateway_v1",
        endpoint_uri="http://gateway.internal:9080",
        capabilities={"pull_punches": True, "historical_pulls": True},
        pull_interval_seconds=300,
    )
    session.add(device)
    session.flush()
    return device


class FakeAdapter:
    adapter_key = "hajiriflow_gateway_v1"

    def __init__(self) -> None:
        self.range_calls = 0

    def capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities(
            pull_punches=True,
            historical_pulls=True,
            list_users=True,
        )

    def diagnostics(self) -> DeviceDiagnostics:
        return DeviceDiagnostics(
            reachable=True,
            observed_at=datetime(2026, 9, 9, 4, 0, tzinfo=UTC),
            firmware_version="1.2.3",
            metadata={"model": "test", "secret_hint": "must-be-redacted"},
        )

    def pull_punches(self, *, cursor: str | None = None) -> PullBatch:
        del cursor
        return PullBatch(
            punches=(
                PunchRecord(
                    external_event_id="live-1",
                    device_user_identifier="42",
                    occurred_at=datetime(2026, 9, 9, 3, 30, tzinfo=UTC),
                    punch_kind="in",
                    evidence={"sequence": 1},
                ),
            ),
            next_cursor=None,
        )

    def pull_punches_range(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
        cursor: str | None = None,
    ) -> PullBatch:
        assert start_at <= end_at
        del cursor
        self.range_calls += 1
        return PullBatch(
            punches=(
                PunchRecord(
                    external_event_id="history-1",
                    device_user_identifier="42",
                    occurred_at=datetime(2026, 9, 8, 3, 30, tzinfo=UTC),
                    punch_kind="out",
                    evidence={"sequence": 2},
                ),
            ),
            next_cursor=None,
        )

    def list_users(self) -> tuple[DeviceUserRecord, ...]:
        return ()


class CursorCycleAdapter(FakeAdapter):
    def pull_punches_range(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
        cursor: str | None = None,
    ) -> PullBatch:
        assert start_at <= end_at
        del cursor
        return PullBatch(punches=(), next_cursor="same")


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.status = 200
        self._body = json.dumps(payload).encode()

    def getheader(self, _name: str) -> str | None:
        return None

    def read(self, _limit: int) -> bytes:
        return self._body


class FakeConnection:
    payloads: dict[str, object] = {}
    requests: list[tuple[str, str, dict[str, str]]] = []

    def __init__(self, _host: str, _port: int | None, *, timeout: int) -> None:
        assert timeout == 7
        self.path = ""

    def request(self, method: str, path: str, *, headers: dict[str, str]) -> None:
        self.path = path
        self.requests.append((method, path, headers))

    def getresponse(self) -> FakeResponse:
        route = self.path.split("?", 1)[0]
        return FakeResponse(self.payloads[route])

    def close(self) -> None:
        return None


def test_gateway_adapter_parses_supported_contract(monkeypatch) -> None:
    FakeConnection.requests = []
    FakeConnection.payloads = {
        "/api/v1/diagnostics": {
            "reachable": True,
            "observed_at": "2026-09-09T04:00:00Z",
            "firmware_version": "2.0",
            "metadata": {"model": "gateway"},
        },
        "/api/v1/punches": {
            "punches": [
                {
                    "external_event_id": "event-1",
                    "device_user_identifier": "42",
                    "occurred_at": "2026-09-09T03:30:00Z",
                    "punch_kind": "in",
                    "evidence": {"sequence": 1},
                }
            ],
            "next_cursor": None,
        },
        "/api/v1/users": {
            "users": [
                {
                    "external_user_id": "42",
                    "display_name": "Employee 42",
                    "template_count": 1,
                }
            ]
        },
    }
    monkeypatch.setattr(
        "hajiriflow.device_platform.gateway_adapter.http.client.HTTPConnection",
        FakeConnection,
    )
    adapter = HajiriFlowGatewayAdapter(
        endpoint_uri="http://gateway.internal:9080/api",
        timeout_seconds=7,
        bearer_token="test-bearer-token",
    )

    assert adapter.capabilities().historical_pulls is True
    assert adapter.diagnostics().reachable is True
    assert adapter.pull_punches().punches[0].external_event_id == "event-1"
    historical = adapter.pull_punches_range(
        start_at=datetime(2026, 9, 8, tzinfo=UTC),
        end_at=datetime(2026, 9, 9, tzinfo=UTC),
    )
    assert historical.punches[0].device_user_identifier == "42"
    assert adapter.list_users()[0].external_user_id == "42"
    assert any(
        "start_at=" in path and "end_at=" in path
        for _, path, _ in FakeConnection.requests
    )
    assert all(
        headers.get("Authorization") == "Bearer test-bearer-token"
        for _, _, headers in FakeConnection.requests
    )


def test_registered_adapter_decrypts_gateway_credential(database) -> None:
    del database
    session = get_session_factory()()
    try:
        organization = _organization(session)
        device = _device(session, organization)
        key = Fernet.generate_key().decode()
        settings = Settings(
            environment="test",
            session_secret="test-secret-that-is-longer-than-thirty-two-characters",
            device_secret_active_key_id="k1",
            device_secret_keys_json=json.dumps({"k1": key}),
        )
        encrypted = build_device_secret_cipher(settings)
        DevicePlatformService(session).rotate_credential(
            device=device,
            secret={"bearer_token": "gateway-secret-token"},
            cipher=encrypted,
            actor_user_id=None,
        )
        adapter = resolve_registered_adapter(
            session=session,
            settings=settings,
            device=device,
        )
        assert isinstance(adapter, HajiriFlowGatewayAdapter)
        unsupported = Device(
            organization_id=organization.id,
            code="OTHER",
            name="Unsupported",
            vendor="Unknown",
            adapter_key="unknown",
            endpoint_uri="http://unknown.internal",
            capabilities={},
        )
        session.add(unsupported)
        session.flush()
        assert (
            resolve_registered_adapter(
                session=session,
                settings=settings,
                device=unsupported,
            )
            is None
        )
    finally:
        session.close()


def test_queued_device_operations_run_only_through_worker_service(database) -> None:
    del database
    session = get_session_factory()()
    try:
        organization = _organization(session)
        device = _device(session, organization)
        service = DeviceOperationService(session, max_attempts=2)
        actor = uuid4()
        adapter = FakeAdapter()

        diagnostics = service.enqueue(
            organization_id=organization.id,
            device_id=device.id,
            operation_type="diagnostics",
            requested_by=actor,
        )
        assert diagnostics.status == "pending"
        service.process(diagnostics, adapter_resolver=lambda _device: adapter)
        assert diagnostics.status == "succeeded"
        assert diagnostics.result_data["metadata"] == {"model": "test"}

        immediate = service.enqueue(
            organization_id=organization.id,
            device_id=device.id,
            operation_type="immediate_pull",
            requested_by=actor,
        )
        service.process(immediate, adapter_resolver=lambda _device: adapter)
        assert immediate.status == "succeeded"
        assert immediate.result_data["ingested_count"] == 1

        historical = service.enqueue(
            organization_id=organization.id,
            device_id=device.id,
            operation_type="historical_pull",
            requested_by=actor,
            window_start=datetime(2026, 9, 8, tzinfo=UTC),
            window_end=datetime(2026, 9, 9, tzinfo=UTC),
        )
        service.process(historical, adapter_resolver=lambda _device: adapter)
        assert historical.status == "succeeded"
        assert historical.result_data["ingested_count"] == 1
        assert adapter.range_calls == 1
        assert len(session.scalars(select(RawPunch)).all()) == 2
    finally:
        session.close()


def test_historical_cursor_cycle_does_not_leave_running_pull(database) -> None:
    del database
    session = get_session_factory()()
    try:
        organization = _organization(session)
        device = _device(session, organization)
        service = DeviceOperationService(session)
        operation = service.enqueue(
            organization_id=organization.id,
            device_id=device.id,
            operation_type="historical_pull",
            requested_by=uuid4(),
            window_start=datetime(2026, 9, 8, tzinfo=UTC),
            window_end=datetime(2026, 9, 9, tzinfo=UTC),
        )
        service.process(
            operation,
            adapter_resolver=lambda _device: CursorCycleAdapter(),
        )
        pull = session.scalar(select(DevicePullSession))
        assert operation.status == "failed"
        assert operation.error_code == "cursor_cycle"
        assert pull is not None
        assert pull.status == "failed"
        assert pull.ended_at is not None
    finally:
        session.close()


def _seed_user(
    *,
    username: str,
    password: str,
    role_code: str,
    organization_id: str | None = None,
) -> None:
    session = get_session_factory()()
    seed_identity_catalog(session)
    service = IdentityService(session, get_settings())
    user = service.create_user(
        username=username,
        display_name=username,
        password=password,
        must_change_password=False,
    )
    service.assign_role(
        user_id=user.id,
        role_code=role_code,
        actor_user_id=user.id,
        scope_type=(ScopeType.ORGANIZATION if organization_id else ScopeType.GLOBAL),
        scope_id=UUID(organization_id) if organization_id else None,
    )
    session.commit()
    session.close()


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def test_device_operations_are_tenant_scoped_and_queued() -> None:
    _seed_user(
        username="system.admin",
        password="system-admin-password-123",
        role_code="system_administrator",
    )
    with TestClient(create_app()) as client:
        system_csrf = _login(client, "system.admin", "system-admin-password-123")
        primary = client.post(
            "/api/v1/organizations",
            headers={"X-CSRF-Token": system_csrf},
            json={
                "legal_name": "Primary Pvt. Ltd.",
                "display_name": "Primary",
                "timezone": "Asia/Kathmandu",
            },
        ).json()
        other = client.post(
            "/api/v1/organizations",
            headers={"X-CSRF-Token": system_csrf},
            json={
                "legal_name": "Other Pvt. Ltd.",
                "display_name": "Other",
                "timezone": "Asia/Kathmandu",
            },
        ).json()
        _seed_user(
            username="device.admin",
            password="device-admin-password-123",
            role_code="workforce_administrator",
            organization_id=primary["id"],
        )
        client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": system_csrf})
        csrf = _login(client, "device.admin", "device-admin-password-123")
        created = client.post(
            f"/api/v1/organizations/{primary['id']}/devices",
            headers={"X-CSRF-Token": csrf},
            json={
                "code": "GATE-1",
                "name": "Main Gate",
                "vendor": "Gateway",
                "adapter_key": "hajiriflow_gateway_v1",
                "endpoint_uri": "http://gateway.internal:9080",
            },
        )
        assert created.status_code == 201, created.text
        device_id = created.json()["id"]

        missing_csrf = client.post(
            f"/api/v1/organizations/{primary['id']}/devices/{device_id}/pull-now"
        )
        assert missing_csrf.status_code == 403
        queued = client.post(
            f"/api/v1/organizations/{primary['id']}/devices/{device_id}/pull-now",
            headers={"X-CSRF-Token": csrf},
        )
        assert queued.status_code == 202, queued.text
        assert queued.json()["status"] == "pending"

        operation_id = queued.json()["id"]
        cross_tenant = client.get(
            f"/api/v1/organizations/{other['id']}/devices/operations/{operation_id}"
        )
        assert cross_tenant.status_code == 403

        session = get_session_factory()()
        try:
            stored = session.get(DeviceOperation, UUID(operation_id))
            assert stored is not None
            assert stored.status == "pending"
        finally:
            session.close()
