from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from hajiriflow.core.config import get_settings
from hajiriflow.db.models.attendance import AttendanceRecord
from hajiriflow.db.models.device import Device, RawPunch
from hajiriflow.db.models.payroll import PayrollLine, PayrollPeriod, PayrollRun
from hajiriflow.db.models.workforce import (
    EmployeeOrganizationAssignment,
    OrganizationNode,
)
from hajiriflow.db.session import get_session_factory
from hajiriflow.identity.bootstrap import seed_identity_catalog
from hajiriflow.identity.permissions import ScopeType
from hajiriflow.identity.service import IdentityService
from hajiriflow.main import create_app

pytestmark = pytest.mark.usefixtures("database")


def _seed_admin() -> UUID:
    session = get_session_factory()()
    seed_identity_catalog(session)
    service = IdentityService(session, get_settings())
    user = service.create_user(
        username="report.admin",
        display_name="Report Admin",
        password="report-admin-password-123",
        must_change_password=False,
    )
    service.assign_role(
        user_id=user.id,
        role_code="system_administrator",
        actor_user_id=user.id,
        scope_type=ScopeType.GLOBAL,
    )
    session.commit()
    user_id = user.id
    session.close()
    return user_id


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "report.admin",
            "password": "report-admin-password-123",
        },
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


def _create_employee(
    client: TestClient,
    csrf: str,
    organization_id: str,
    code: str,
    name: str,
) -> dict:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/employees",
        headers={"X-CSRF-Token": csrf},
        json={
            "employee_code": code,
            "display_name": name,
            "joined_on": "2026-01-01",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_reports_are_org_scoped_complete_and_privacy_safe() -> None:
    admin_id = _seed_admin()
    with TestClient(create_app()) as client:
        csrf = _login(client)
        company = _create_company(client, csrf, "Reporting Tenant")
        other = _create_company(client, csrf, "Other Reporting Tenant")
        employee = _create_employee(
            client,
            csrf,
            company["id"],
            "EMP-REP-1",
            "Mina Rai",
        )
        _create_employee(
            client,
            csrf,
            company["id"],
            "EMP-REP-2",
            "Asha Gurung",
        )

        session = get_session_factory()()
        try:
            department = OrganizationNode(
                organization_id=UUID(company["id"]),
                node_type="department",
                code="FIN",
                name="Finance",
            )
            session.add(department)
            session.flush()
            session.add(
                EmployeeOrganizationAssignment(
                    organization_id=UUID(company["id"]),
                    employee_id=UUID(employee["id"]),
                    organization_node_id=department.id,
                    starts_on=date(2026, 1, 1),
                    is_primary=True,
                )
            )
            session.add(
                AttendanceRecord(
                    organization_id=UUID(company["id"]),
                    employee_id=UUID(employee["id"]),
                    work_date=date(2026, 9, 7),
                    check_in_at=datetime(2026, 9, 7, 3, 15, tzinfo=UTC),
                    check_out_at=datetime(2026, 9, 7, 11, 15, tzinfo=UTC),
                    worked_minutes=480,
                    late_minutes=5,
                    status="present",
                    calculation_version="attendance-v1",
                    source_punch_count=2,
                    source_revision=1,
                )
            )
            device = Device(
                organization_id=UUID(company["id"]),
                code="REPORT-DEVICE",
                name="Report Device",
                vendor="Unspecified",
                adapter_key="unsupported-report-adapter",
                endpoint_uri="device://report",
                capabilities={"pull_punches": True},
            )
            session.add(device)
            session.flush()
            session.add(
                RawPunch(
                    organization_id=UUID(company["id"]),
                    device_id=device.id,
                    external_event_id="evt-1",
                    device_user_identifier="external-101",
                    occurred_at=datetime(2026, 9, 7, 3, 15, tzinfo=UTC),
                    punch_kind="in",
                    verification_method="device",
                    source_fingerprint="b" * 64,
                    evidence={"terminal": "front-gate"},
                )
            )
            period = PayrollPeriod(
                organization_id=UUID(company["id"]),
                code="2083-05",
                label="Bhadra 2083",
                starts_on=date(2026, 8, 17),
                ends_on=date(2026, 9, 16),
                attendance_calculation_version="attendance-v1",
                created_by=admin_id,
            )
            session.add(period)
            session.flush()
            run = PayrollRun(
                organization_id=UUID(company["id"]),
                period_id=period.id,
                sequence=1,
                status="draft",
                calculation_version="payroll-v1",
                policy_snapshot={"policy": "fixture"},
                created_by=admin_id,
            )
            session.add(run)
            session.flush()
            session.add(
                PayrollLine(
                    run_id=run.id,
                    employee_id=UUID(employee["id"]),
                    gross_amount=Decimal("100000.00"),
                    deduction_amount=Decimal("5000.00"),
                    tax_amount=Decimal("10000.00"),
                    net_amount=Decimal("85000.00"),
                    employee_snapshot={"employee_code": "EMP-REP-1"},
                    attendance_snapshot={"calculation_version": "attendance-v1"},
                    earnings_snapshot={"base": "100000.00"},
                    deductions_snapshot={"other": "5000.00"},
                    explanation={"basis": "fixture"},
                )
            )
            session.commit()
            run_id = str(run.id)
        finally:
            session.close()

        daily = client.get(
            f"/api/v1/organizations/{company['id']}/reports/daily",
            params={"work_date": "2026-09-07"},
        )
        assert daily.status_code == 200, daily.text
        assert [row["status"] for row in daily.json()] == ["present", "uncalculated"]

        absent = client.get(
            f"/api/v1/organizations/{company['id']}/reports/daily",
            params={"work_date": "2026-09-07", "only_absent": "true"},
        )
        assert absent.status_code == 200, absent.text
        assert absent.json() == []

        summary = client.get(
            f"/api/v1/organizations/{company['id']}/reports/summary",
            params={"from_date": "2026-09-07", "to_date": "2026-09-07"},
        )
        assert summary.status_code == 200, summary.text
        assert summary.json()["employee_count"] == 2
        assert summary.json()["present_records"] == 1
        assert summary.json()["worked_minutes"] == 480

        detail = client.get(
            f"/api/v1/organizations/{company['id']}/reports/employees/"
            f"{employee['id']}/detail",
            params={"from_date": "2026-09-07", "to_date": "2026-09-08"},
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["present_days"] == 1
        assert detail.json()["uncalculated_days"] == 1

        coverage = client.get(
            f"/api/v1/organizations/{company['id']}/reports/department-coverage",
            params={"work_date": "2026-09-07"},
        )
        assert coverage.status_code == 200, coverage.text
        by_name = {row["department_name"]: row for row in coverage.json()}
        assert by_name["Finance"]["present"] == 1
        assert by_name["Unassigned"]["uncalculated"] == 1

        register = client.get(
            f"/api/v1/organizations/{company['id']}/reports/hajiri-register",
            params={"from_date": "2026-09-07", "to_date": "2026-09-08"},
        )
        assert register.status_code == 200, register.text
        employee_row = next(
            row for row in register.json() if row["employee_id"] == employee["id"]
        )
        assert employee_row["days"] == {
            "2026-09-07": "present",
            "2026-09-08": "uncalculated",
        }

        events = client.get(
            f"/api/v1/organizations/{company['id']}/reports/attendance-events"
        )
        assert events.status_code == 200, events.text
        assert events.json()[0]["source_fingerprint"] == "b" * 64
        assert "evidence" not in events.json()[0]
        assert "device_user_identifier" not in events.json()[0]

        worksheet = client.get(
            f"/api/v1/organizations/{company['id']}/reports/payroll/{run_id}/worksheet"
        )
        assert worksheet.status_code == 200, worksheet.text
        assert worksheet.json()["calculation_version"] == "payroll-v1"
        assert worksheet.json()["attendance_calculation_version"] == "attendance-v1"
        assert worksheet.json()["rows"][0]["net_amount"] == "85000.00"

        other_tenant = client.get(
            f"/api/v1/organizations/{other['id']}/reports/daily",
            params={"work_date": "2026-09-07"},
        )
        assert other_tenant.status_code == 200
        assert other_tenant.json() == []
