import json
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from hajiriflow.core.config import get_settings
from hajiriflow.db.models.device import Device
from hajiriflow.db.models.identity import AuditEvent, UserAccount
from hajiriflow.db.models.workforce import CompanyProfile, Employee
from hajiriflow.db.session import get_session_factory
from hajiriflow.identity.bootstrap import ROLES, seed_identity_catalog
from hajiriflow.identity.permissions import ScopeType
from hajiriflow.identity.service import IdentityService
from hajiriflow.main import create_app
from hajiriflow.operations.service import OperationalDashboardService

pytestmark = pytest.mark.usefixtures("database")


def _seed_identity():
    session = get_session_factory()()
    seed_identity_catalog(session)
    identity = IdentityService(session, get_settings())
    organization = CompanyProfile(
        legal_name="Final Baseline Pvt. Ltd.",
        display_name="Final Baseline",
        timezone="Asia/Kathmandu",
    )
    other = CompanyProfile(
        legal_name="Other Baseline Pvt. Ltd.",
        display_name="Other Baseline",
        timezone="Asia/Kathmandu",
    )
    session.add_all([organization, other])
    session.flush()
    employee = Employee(
        organization_id=organization.id,
        employee_code="EMP-LINK-1",
        display_name="Linked Employee",
        joined_on=date(2026, 1, 1),
    )
    other_employee = Employee(
        organization_id=organization.id,
        employee_code="EMP-LINK-2",
        display_name="Second Employee",
        joined_on=date(2026, 1, 1),
    )
    session.add_all([employee, other_employee])
    session.flush()
    system = identity.create_user(
        username="final.system",
        display_name="Final System",
        password="final-system-password-123",
        must_change_password=False,
    )
    target = identity.create_user(
        username="final.target",
        display_name="Final Target",
        password="final-target-password-123",
        must_change_password=False,
    )
    employee_user = identity.create_user(
        username="final.employee",
        display_name="Final Employee",
        password="final-employee-password-123",
        must_change_password=False,
    )
    workforce = identity.create_user(
        username="final.workforce",
        display_name="Final Workforce",
        password="final-workforce-password-123",
        must_change_password=False,
    )
    employee_user.employee_id = employee.id
    identity.assign_role(
        user_id=system.id,
        role_code="system_administrator",
        actor_user_id=system.id,
        scope_type=ScopeType.GLOBAL,
    )
    identity.assign_role(
        user_id=employee_user.id,
        role_code="employee",
        actor_user_id=system.id,
        scope_type=ScopeType.ORGANIZATION,
        scope_id=organization.id,
    )
    identity.assign_role(
        user_id=workforce.id,
        role_code="workforce_administrator",
        actor_user_id=system.id,
        scope_type=ScopeType.ORGANIZATION,
        scope_id=organization.id,
    )
    session.commit()
    result = {
        "organization_id": organization.id,
        "other_organization_id": other.id,
        "employee_id": employee.id,
        "other_employee_id": other_employee.id,
        "system_id": system.id,
        "target_id": target.id,
        "employee_user_id": employee_user.id,
        "workforce_id": workforce.id,
    }
    session.close()
    return result


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def test_account_search_edit_linking_and_audit_reader_are_authoritative() -> None:
    ids = _seed_identity()
    with TestClient(create_app()) as client:
        csrf = _login(client, "final.system", "final-system-password-123")
        search = client.get("/api/v1/admin/users/search", params={"q": "target"})
        assert search.status_code == 200, search.text
        assert [row["id"] for row in search.json()] == [str(ids["target_id"])]

        employees = client.get(
            "/api/v1/admin/employee-links",
            params={"q": "EMP-LINK", "organization_id": str(ids["organization_id"])},
        )
        assert employees.status_code == 200, employees.text
        assert {row["id"] for row in employees.json()} == {
            str(ids["employee_id"]),
            str(ids["other_employee_id"]),
        }

        updated = client.patch(
            f"/api/v1/admin/users/{ids['target_id']}",
            headers={"X-CSRF-Token": csrf},
            json={
                "username": "final.target.updated",
                "display_name": "Updated Target",
                "employee_id": str(ids["other_employee_id"]),
            },
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["employee_id"] == str(ids["other_employee_id"])

        duplicate = client.patch(
            f"/api/v1/admin/users/{ids['employee_user_id']}",
            headers={"X-CSRF-Token": csrf},
            json={"employee_id": str(ids["other_employee_id"])},
        )
        assert duplicate.status_code == 400
        assert "already linked" in duplicate.json()["detail"]

        audit = client.get(
            "/api/v1/admin/audit-events",
            params={"action_prefix": "identity.user", "object_id": str(ids["target_id"])},
        )
        assert audit.status_code == 200, audit.text
        assert any(row["action"] == "identity.user.updated" for row in audit.json())
        event = next(row for row in audit.json() if row["action"] == "identity.user.updated")
        assert event["after_data"]["employee_id"] == str(ids["other_employee_id"])
        assert "password" not in json.dumps(event).lower()

    session = get_session_factory()()
    target = session.get(UserAccount, ids["target_id"])
    assert target is not None
    assert target.username == "final.target.updated"
    assert target.session_version == 2
    event_model = session.scalar(
        select(AuditEvent)
        .where(AuditEvent.action == "identity.user.updated")
        .order_by(AuditEvent.occurred_at.desc())
    )
    assert event_model is not None
    event_model.action = "tampered"
    with pytest.raises(RuntimeError, match="immutable"):
        session.flush()
    session.rollback()
    event_model = session.get(AuditEvent, event_model.id)
    session.delete(event_model)
    with pytest.raises(RuntimeError, match="immutable"):
        session.flush()
    session.rollback()
    session.close()


def test_operations_dashboard_is_org_scoped_sanitized_and_role_bounded() -> None:
    ids = _seed_identity()
    session = get_session_factory()()
    device = Device(
        organization_id=ids["organization_id"],
        code="OPS-DEVICE",
        name="Operations device",
        vendor="Gateway",
        adapter_key="hajiriflow_gateway_v1",
        endpoint_uri="https://device.internal.invalid",
        capabilities={"pull_punches": True},
        pull_interval_seconds=300,
        status="active",
    )
    session.add(device)
    session.commit()
    snapshot = OperationalDashboardService(session).snapshot(
        organization_id=ids["organization_id"],
        work_date=date(2026, 9, 9),
    )
    assert snapshot["devices"]["total"] == 1
    assert snapshot["devices"]["stale"] == 1
    assert any(alert["code"] == "stale_devices" for alert in snapshot["alerts"])
    serialized = json.dumps(snapshot).lower()
    for sensitive in (
        "endpoint_uri",
        "password",
        "credential",
        "bearer_token",
        "biometric_payload",
        "bank_account",
        "base_salary",
    ):
        assert sensitive not in serialized
    session.close()

    with TestClient(create_app()) as client:
        employee_csrf = _login(
            client,
            "final.employee",
            "final-employee-password-123",
        )
        denied = client.get(
            f"/api/v1/organizations/{ids['organization_id']}/operations/dashboard"
        )
        assert denied.status_code == 403
        audit_denied = client.get("/api/v1/admin/audit-events")
        assert audit_denied.status_code == 403
        accounts_denied = client.get("/api/v1/admin/users/search")
        assert accounts_denied.status_code == 403
        self_payroll = client.get(
            f"/api/v1/organizations/{ids['organization_id']}/payroll-v2/self/payslips"
        )
        assert self_payroll.status_code == 200

        logout = client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": employee_csrf},
        )
        assert logout.status_code == 204
        _login(client, "final.workforce", "final-workforce-password-123")
        allowed = client.get(
            f"/api/v1/organizations/{ids['organization_id']}/operations/dashboard"
        )
        assert allowed.status_code == 200, allowed.text
        cross_tenant = client.get(
            f"/api/v1/organizations/{ids['other_organization_id']}/operations/dashboard"
        )
        assert cross_tenant.status_code == 403
        assert "endpoint_uri" not in allowed.text


def test_role_catalog_keeps_admin_and_self_service_boundaries_separate() -> None:
    employee_permissions = set(ROLES["employee"]["permissions"])
    workforce_permissions = set(ROLES["workforce_administrator"]["permissions"])
    payroll_permissions = set(ROLES["payroll_administrator"]["permissions"])
    assert {"attendance.self.read", "payroll.self.read"} <= employee_permissions
    assert "attendance.export" not in employee_permissions
    assert "payroll.export" not in employee_permissions
    assert "device.pull" not in employee_permissions
    assert "operations.read" not in employee_permissions
    workforce_required = {
        "employee.export",
        "attendance.export",
        "device.pull",
        "operations.read",
    }
    assert workforce_required <= workforce_permissions
    assert "payroll.manage" not in workforce_permissions
    payroll_required = {
        "payroll.read",
        "payroll.manage",
        "payroll.approve",
        "payroll.export",
        "operations.read",
    }
    assert payroll_required <= payroll_permissions
    assert "identity.user.manage" not in payroll_permissions
