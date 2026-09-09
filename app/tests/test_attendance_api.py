from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from hajiriflow.core.config import get_settings
from hajiriflow.db.session import get_session_factory
from hajiriflow.identity.bootstrap import seed_identity_catalog
from hajiriflow.identity.permissions import ScopeType
from hajiriflow.identity.service import IdentityService
from hajiriflow.main import create_app

pytestmark = pytest.mark.usefixtures("database")


def _seed_admin(
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


def _create_company(client: TestClient, csrf: str, name: str) -> dict:
    response = client.post(
        "/api/v1/organizations",
        headers={"X-CSRF-Token": csrf},
        json={
            "legal_name": f"{name} Pvt. Ltd.",
            "display_name": name,
            "timezone": "Asia/Kathmandu",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_employee(client: TestClient, csrf: str, organization_id: str) -> dict:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/employees",
        headers={"X-CSRF-Token": csrf},
        json={
            "employee_code": "EMP-001",
            "display_name": "Asha Rai",
            "joined_on": "2026-01-01",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_attendance_api_routes_v2_corrections_through_manual_events() -> None:
    _seed_admin(
        username="system.admin",
        password="system-admin-password-123",
        role_code="system_administrator",
    )
    with TestClient(create_app()) as client:
        system_csrf = _login(
            client,
            "system.admin",
            "system-admin-password-123",
        )
        primary = _create_company(client, system_csrf, "Primary Tenant")
        other = _create_company(client, system_csrf, "Other Tenant")
        employee = _create_employee(client, system_csrf, primary["id"])

        _seed_admin(
            username="attendance.maker",
            password="attendance-maker-password-123",
            role_code="workforce_administrator",
            organization_id=primary["id"],
        )
        _seed_admin(
            username="attendance.checker",
            password="attendance-checker-password-123",
            role_code="workforce_administrator",
            organization_id=primary["id"],
        )

        client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": system_csrf},
        )
        maker_csrf = _login(
            client,
            "attendance.maker",
            "attendance-maker-password-123",
        )

        denied = client.get(
            f"/api/v1/organizations/{other['id']}/attendance/records"
        )
        assert denied.status_code == 403

        calculated = client.post(
            f"/api/v1/organizations/{primary['id']}/attendance/calculate",
            headers={"X-CSRF-Token": maker_csrf},
            json={
                "employee_id": employee["id"],
                "work_date": "2026-09-07",
            },
        )
        assert calculated.status_code == 200, calculated.text
        record = calculated.json()
        assert record["status"] == "absent"
        assert record["source_revision"] == 1
        assert record["calculation_version"] == "attendance-v2"

        missing_csrf = client.post(
            f"/api/v1/organizations/{primary['id']}/attendance/"
            f"records/{record['id']}/corrections",
            json={"reason": "Approved field evidence was received."},
        )
        assert missing_csrf.status_code == 403

        legacy = client.post(
            f"/api/v1/organizations/{primary['id']}/attendance/"
            f"records/{record['id']}/corrections",
            headers={"X-CSRF-Token": maker_csrf},
            json={
                "reason": "Approved field evidence was received.",
                "proposed_status": "present",
                "proposed_check_in_at": "2026-09-07T03:15:00Z",
                "proposed_check_out_at": "2026-09-07T11:15:00Z",
            },
        )
        assert legacy.status_code == 409, legacy.text
        assert "additive manual events" in legacy.json()["detail"]

        manual_events = []
        for event_type, event_time in (
            ("in", "2026-09-07T03:15:00Z"),
            ("out", "2026-09-07T11:15:00Z"),
        ):
            requested = client.post(
                f"/api/v1/organizations/{primary['id']}/attendance-v2/manual-events",
                headers={"X-CSRF-Token": maker_csrf},
                json={
                    "employee_id": employee["id"],
                    "event_time": event_time,
                    "event_type": event_type,
                    "reason": "Approved field evidence was received.",
                    "evidence_note": "Supervisor verified the attendance event.",
                },
            )
            assert requested.status_code == 201, requested.text
            manual_events.append(requested.json())

        self_approval = client.post(
            f"/api/v1/organizations/{primary['id']}/attendance-v2/"
            f"manual-events/{manual_events[0]['id']}/decision",
            headers={"X-CSRF-Token": maker_csrf},
            json={"approve": True, "reason": "Evidence checked."},
        )
        assert self_approval.status_code == 400
        assert "independent approval" in self_approval.json()["detail"]

        client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": maker_csrf},
        )
        checker_csrf = _login(
            client,
            "attendance.checker",
            "attendance-checker-password-123",
        )
        for item in manual_events:
            approved = client.post(
                f"/api/v1/organizations/{primary['id']}/attendance-v2/"
                f"manual-events/{item['id']}/decision",
                headers={"X-CSRF-Token": checker_csrf},
                json={"approve": True, "reason": "Evidence checked."},
            )
            assert approved.status_code == 200, approved.text
            assert approved.json()["status"] == "approved"
            assert approved.json()["decided_by"] is not None

        recalculated = client.post(
            f"/api/v1/organizations/{primary['id']}/attendance-v2/engine/"
            f"{employee['id']}/2026-09-07/calculate",
            headers={"X-CSRF-Token": checker_csrf},
        )
        assert recalculated.status_code == 200, recalculated.text
        assert recalculated.json()["base_status"] == "present"
        assert recalculated.json()["source_revision"] == 2
        assert recalculated.json()["engine_version"] == "attendance-v2"

        records = client.get(
            f"/api/v1/organizations/{primary['id']}/attendance/records",
            params={"status": "present"},
        )
        assert records.status_code == 200, records.text
        assert len(records.json()) == 1
        assert records.json()[0]["source_revision"] == 2

        history = client.get(
            f"/api/v1/organizations/{primary['id']}/attendance/"
            f"records/{record['id']}/history"
        )
        assert history.status_code == 200, history.text
        assert [item["event_type"] for item in history.json()] == [
            "calculated",
            "recalculated",
        ]
        assert all(item["correction_id"] is None for item in history.json())
