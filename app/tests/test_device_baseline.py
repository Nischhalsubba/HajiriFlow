import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from hajiriflow.core.config import get_settings
from hajiriflow.db.models.device import Device, DeviceUser, RawPunch
from hajiriflow.db.models.device_baseline import (
    DeviceDiagnosticSnapshot,
    DeviceIdentityArchive,
    DeviceJob,
)
from hajiriflow.db.models.workforce import CompanyProfile
from hajiriflow.db.session import get_session_factory
from hajiriflow.device_platform.adapters import (
    DeviceCapabilities,
    DeviceDiagnostics,
    DeviceUserRecord,
    PullBatch,
    PunchRecord,
)
from hajiriflow.device_platform.crypto import DeviceSecretCipher
from hajiriflow.device_platform.gateway_v1 import HajiriFlowGatewayV1Adapter
from hajiriflow.device_platform.jobs import DeviceJobProcessor, DeviceJobService
from hajiriflow.identity.bootstrap import seed_identity_catalog
from hajiriflow.identity.permissions import ScopeType
from hajiriflow.identity.service import IdentityService
from hajiriflow.main import create_app

pytestmark = pytest.mark.usefixtures("database")


class FakeDeviceAdapter:
    adapter_key = "fake"

    def __init__(self, name: str) -> None:
        self.name = name
        self.users: dict[str, DeviceUserRecord] = {}
        self.restored_archives: list[bytes] = []
        self.pull_number = 0

    def capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities(
            pull_punches=True,
            list_users=True,
            push_users=True,
            biometric_templates=True,
        )

    def diagnostics(self) -> DeviceDiagnostics:
        return DeviceDiagnostics(
            reachable=True,
            observed_at=datetime(2026, 9, 8, 8, 0, tzinfo=UTC),
            firmware_version="gateway-test-1",
            message="reachable",
            metadata={"latency_ms": 12},
        )

    def pull_punches(
        self,
        *,
        cursor: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> PullBatch:
        del cursor, start_at, end_at
        self.pull_number += 1
        return PullBatch(
            punches=(
                PunchRecord(
                    external_event_id=f"{self.name}-event-{self.pull_number}",
                    device_user_identifier="1001",
                    occurred_at=datetime(2026, 9, 8, 8, self.pull_number, tzinfo=UTC),
                    punch_kind="in",
                    evidence={"sequence": self.pull_number},
                ),
            ),
            next_cursor=f"cursor-{self.pull_number}",
        )

    def list_users(self) -> tuple[DeviceUserRecord, ...]:
        return tuple(self.users.values())

    def push_user(
        self,
        record: DeviceUserRecord,
        *,
        overwrite: bool = False,
    ) -> DeviceUserRecord:
        if record.external_user_id in self.users and not overwrite:
            raise ValueError("user already exists")
        self.users[record.external_user_id] = record
        return record

    def export_user_archive(self, external_user_id: str) -> bytes:
        return f"biometric-template-for:{external_user_id}".encode()

    def import_user_archive(
        self,
        archive: bytes,
        *,
        overwrite: bool = False,
    ) -> DeviceUserRecord:
        del overwrite
        self.restored_archives.append(archive)
        external_user_id = archive.decode().rsplit(":", 1)[-1]
        record = DeviceUserRecord(
            external_user_id=external_user_id,
            display_name="Restored User",
        )
        self.users[external_user_id] = record
        return record


def _organization(session, name: str = "Device Org") -> CompanyProfile:
    item = CompanyProfile(legal_name=name, display_name=name)
    session.add(item)
    session.flush()
    return item


def _device(session, organization: CompanyProfile, code: str) -> Device:
    item = Device(
        organization_id=organization.id,
        code=code,
        name=f"Device {code}",
        vendor="gateway",
        model="v1",
        serial_number=f"serial-{code}",
        adapter_key="fake",
        endpoint_uri=f"https://{code}.example.test",
        capabilities={
            "pull_punches": True,
            "list_users": True,
            "push_users": True,
            "biometric_templates": True,
        },
    )
    session.add(item)
    session.flush()
    return item


def test_gateway_v1_normalizes_contract_without_vendor_assumptions(monkeypatch) -> None:
    adapter = HajiriFlowGatewayV1Adapter(
        endpoint_uri="https://gateway.example.test",
        token="secret-token",
    )

    def fake_request(method, path, *, query=None, payload=None):
        del method, query, payload
        if path == "/v1/diagnostics":
            return {
                "reachable": True,
                "observed_at": "2026-09-08T08:00:00Z",
                "firmware_version": "gw-1",
                "capabilities": {
                    "pull_punches": True,
                    "list_users": True,
                    "push_users": True,
                    "biometric_templates": True,
                },
            }
        if path == "/v1/punches":
            return {
                "punches": [
                    {
                        "external_event_id": "evt-1",
                        "device_user_identifier": "42",
                        "occurred_at": "2026-09-08T08:30:00+05:45",
                        "punch_kind": "in",
                        "evidence": {"sequence": 1},
                    }
                ],
                "next_cursor": "next-1",
            }
        if path == "/v1/users":
            return {
                "users": [
                    {
                        "external_user_id": "42",
                        "display_name": "User 42",
                        "active": True,
                        "template_count": 1,
                    }
                ]
            }
        if path.endswith("/archive"):
            return {"archive_base64": base64.b64encode(b"archive-42").decode()}
        if path == "/v1/users/archive":
            return {"user": {"external_user_id": "42", "display_name": "Restored"}}
        return {"user": {"external_user_id": "42", "display_name": "User 42"}}

    monkeypatch.setattr(adapter, "_request_json", fake_request)
    assert adapter.capabilities().biometric_templates is True
    assert adapter.diagnostics().reachable is True
    batch = adapter.pull_punches(
        start_at=datetime(2026, 9, 1, tzinfo=UTC),
        end_at=datetime(2026, 9, 8, tzinfo=UTC),
    )
    assert batch.next_cursor == "next-1"
    assert batch.punches[0].device_user_identifier == "42"
    assert adapter.list_users()[0].template_count == 1
    assert adapter.push_user(DeviceUserRecord(external_user_id="42")).external_user_id == "42"
    assert adapter.export_user_archive("42") == b"archive-42"
    assert adapter.import_user_archive(b"archive-42").external_user_id == "42"


def test_persistent_device_jobs_run_in_worker_and_archive_is_encrypted() -> None:
    session = get_session_factory()()
    try:
        organization = _organization(session)
        source = _device(session, organization, "source")
        target = _device(session, organization, "target")
        source_adapter = FakeDeviceAdapter("source")
        target_adapter = FakeDeviceAdapter("target")
        source_adapter.users["1001"] = DeviceUserRecord(
            external_user_id="1001",
            display_name="Gateway User",
        )
        cipher = DeviceSecretCipher(
            active_key_id="archive-k1",
            keys={"archive-k1": Fernet.generate_key()},
        )
        processor = DeviceJobProcessor(
            session,
            adapter_resolver=lambda device: (
                source_adapter if device.id == source.id else target_adapter
            ),
            settings=get_settings(),
            archive_cipher=cipher,
        )
        queue = DeviceJobService(session)

        diagnostics = queue.enqueue(
            device=source,
            job_type="diagnostics",
            payload={},
            requested_by=None,
        )
        immediate = queue.enqueue(
            device=source,
            job_type="immediate_pull",
            payload={},
            requested_by=None,
        )
        historical = queue.enqueue(
            device=source,
            job_type="historical_pull",
            payload={
                "start_at": datetime(2026, 9, 1, tzinfo=UTC).isoformat(),
                "end_at": datetime(2026, 9, 8, tzinfo=UTC).isoformat(),
            },
            requested_by=None,
        )
        sync = queue.enqueue(
            device=source,
            job_type="sync_users",
            payload={},
            requested_by=None,
        )
        push = queue.enqueue(
            device=target,
            job_type="push_user",
            payload={"external_user_id": "2001", "display_name": "Pushed"},
            requested_by=None,
        )
        session.flush()

        for job in (diagnostics, immediate, historical, sync, push):
            processor.process(job)
            assert job.status == "succeeded", (job.job_type, job.error_code)

        source_user = session.scalar(
            select(DeviceUser).where(
                DeviceUser.device_id == source.id,
                DeviceUser.external_user_id == "1001",
            )
        )
        assert source_user is not None

        migration = queue.enqueue(
            device=source,
            job_type="migrate_user",
            payload={
                "target_device_id": str(target.id),
                "external_user_id": "1001",
            },
            requested_by=None,
        )
        processor.process(migration)
        assert migration.status == "succeeded"
        assert "1001" in target_adapter.users

        conflicting = queue.enqueue(
            device=source,
            job_type="migrate_user",
            payload={
                "target_device_id": str(target.id),
                "external_user_id": "1001",
            },
            requested_by=None,
        )
        processor.process(conflicting)
        assert conflicting.status == "failed"

        archive_job = queue.enqueue(
            device=source,
            job_type="archive_user",
            payload={"external_user_id": "1001"},
            requested_by=None,
        )
        processor.process(archive_job)
        assert archive_job.status == "succeeded"
        archive = session.get(
            DeviceIdentityArchive,
            UUID(archive_job.result["archive_id"]),
        )
        assert archive is not None
        assert b"biometric-template-for:1001" not in archive.ciphertext

        restore_job = queue.enqueue(
            device=target,
            job_type="restore_user",
            payload={"archive_id": str(archive.id)},
            requested_by=None,
        )
        processor.process(restore_job)
        assert restore_job.status == "succeeded"
        assert target_adapter.restored_archives == [b"biometric-template-for:1001"]

        assert session.scalar(select(DeviceDiagnosticSnapshot.id)) is not None
        assert session.scalar(select(RawPunch.id)) is not None
    finally:
        session.close()


def _seed_system_admin() -> None:
    session = get_session_factory()()
    seed_identity_catalog(session)
    service = IdentityService(session, get_settings())
    user = service.create_user(
        username="system.admin",
        display_name="System Admin",
        password="system-admin-password-123",
        must_change_password=False,
    )
    service.assign_role(
        user_id=user.id,
        role_code="system_administrator",
        actor_user_id=user.id,
        scope_type=ScopeType.GLOBAL,
    )
    session.commit()
    session.close()


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "system.admin",
            "password": "system-admin-password-123",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def test_device_api_queues_worker_operations_and_reviews_unlinked_punches(monkeypatch) -> None:
    _seed_system_admin()
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("HAJIRIFLOW_DEVICE_SECRET_ACTIVE_KEY_ID", "k1")
    monkeypatch.setenv(
        "HAJIRIFLOW_DEVICE_SECRET_KEYS_JSON",
        json.dumps({"k1": key}),
    )
    with TestClient(create_app()) as client:
        csrf = _login(client)
        company = client.post(
            "/api/v1/organizations",
            headers={"X-CSRF-Token": csrf},
            json={
                "legal_name": "Device API Pvt. Ltd.",
                "display_name": "Device API",
                "timezone": "Asia/Kathmandu",
            },
        )
        assert company.status_code == 201, company.text
        org_id = company.json()["id"]
        device = client.post(
            f"/api/v1/organizations/{org_id}/devices",
            headers={"X-CSRF-Token": csrf},
            json={
                "code": "GATE-1",
                "name": "Gate 1",
                "vendor": "HajiriFlow Gateway",
                "model": "v1",
                "serial_number": "GW-001",
                "adapter_key": "hajiriflow_gateway_v1",
                "endpoint_uri": "https://gateway.example.test",
                "capabilities": {
                    "pull_punches": True,
                    "list_users": True,
                    "push_users": True,
                    "biometric_templates": True,
                },
                "pull_interval_seconds": 300,
            },
        )
        assert device.status_code == 201, device.text
        device_id = device.json()["id"]

        credential = client.post(
            f"/api/v1/organizations/{org_id}/device-platform/devices/"
            f"{device_id}/credentials/rotate",
            headers={"X-CSRF-Token": csrf},
            json={"token": "gateway-access-token"},
        )
        assert credential.status_code == 200, credential.text
        assert "gateway-access-token" not in credential.text

        diagnostics = client.post(
            f"/api/v1/organizations/{org_id}/device-platform/devices/"
            f"{device_id}/diagnostics",
            headers={"X-CSRF-Token": csrf},
        )
        assert diagnostics.status_code == 200, diagnostics.text
        assert diagnostics.json()["status"] == "queued"

        historical = client.post(
            f"/api/v1/organizations/{org_id}/device-platform/devices/"
            f"{device_id}/pull/historical",
            headers={"X-CSRF-Token": csrf},
            json={
                "start_at": "2026-09-01T00:00:00Z",
                "end_at": "2026-09-08T00:00:00Z",
            },
        )
        assert historical.status_code == 200, historical.text
        assert historical.json()["status"] == "queued"

        session = get_session_factory()()
        registered = session.get(Device, UUID(device_id))
        assert registered is not None
        session.add(
            RawPunch(
                organization_id=UUID(org_id),
                device_id=registered.id,
                external_event_id="unlinked-1",
                device_user_identifier="unmapped-user",
                occurred_at=datetime(2026, 9, 8, 8, 0, tzinfo=UTC),
                punch_kind="in",
                source_fingerprint="a" * 64,
                evidence={"sequence": 1},
            )
        )
        session.commit()
        session.close()

        unlinked = client.get(
            f"/api/v1/organizations/{org_id}/device-platform/unlinked-punches"
        )
        assert unlinked.status_code == 200, unlinked.text
        assert unlinked.json()[0]["device_user_identifier"] == "unmapped-user"

        jobs = client.get(f"/api/v1/organizations/{org_id}/device-platform/jobs")
        assert jobs.status_code == 200, jobs.text
        assert {item["job_type"] for item in jobs.json()} == {
            "diagnostics",
            "historical_pull",
        }
        assert all(item["status"] == "queued" for item in jobs.json())
