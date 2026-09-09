from datetime import date
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from hajiriflow.core.config import get_settings
from hajiriflow.db.models.payroll_baseline import FiscalYear, PayrollPeriodContext
from hajiriflow.db.models.workforce import CompanyProfile, Employee
from hajiriflow.db.session import get_session_factory
from hajiriflow.identity.bootstrap import seed_identity_catalog
from hajiriflow.identity.permissions import FULL_ACCESS, PermissionGrant, ScopeType
from hajiriflow.identity.service import IdentityService
from hajiriflow.main import create_app
from hajiriflow.payroll.service import PayrollService

pytestmark = pytest.mark.usefixtures("database")


def _full_access() -> frozenset[PermissionGrant]:
    return frozenset({PermissionGrant(FULL_ACCESS)})


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def _seed_posted_payroll():
    session = get_session_factory()()
    seed_identity_catalog(session)
    identity = IdentityService(session, get_settings())
    organization = CompanyProfile(
        legal_name="Self Service Pvt. Ltd.",
        display_name="Self Service",
        timezone="Asia/Kathmandu",
    )
    session.add(organization)
    session.flush()
    employee_a = Employee(
        organization_id=organization.id,
        employee_code="SELF-A",
        display_name="Employee A",
        joined_on=date(2026, 1, 1),
    )
    employee_b = Employee(
        organization_id=organization.id,
        employee_code="SELF-B",
        display_name="Employee B",
        joined_on=date(2026, 1, 1),
    )
    session.add_all([employee_a, employee_b])
    session.flush()
    maker = identity.create_user(
        username="payroll.maker.self",
        display_name="Maker",
        password="maker-password-123",
        must_change_password=False,
    )
    checker = identity.create_user(
        username="payroll.checker.self",
        display_name="Checker",
        password="checker-password-123",
        must_change_password=False,
    )
    user_a = identity.create_user(
        username="employee.a",
        display_name="Employee A",
        password="employee-a-password-123",
        must_change_password=False,
    )
    user_b = identity.create_user(
        username="employee.b",
        display_name="Employee B",
        password="employee-b-password-123",
        must_change_password=False,
    )
    user_a.employee_id = employee_a.id
    user_b.employee_id = employee_b.id
    identity.assign_role(
        user_id=user_a.id,
        role_code="employee",
        actor_user_id=maker.id,
        scope_type=ScopeType.ORGANIZATION,
        scope_id=organization.id,
    )
    identity.assign_role(
        user_id=user_b.id,
        role_code="employee",
        actor_user_id=maker.id,
        scope_type=ScopeType.ORGANIZATION,
        scope_id=organization.id,
    )
    grants = _full_access()
    payroll = PayrollService(session)
    period = payroll.create_period(
        organization_id=organization.id,
        code="2083-05",
        label="Bhadra 2083",
        starts_on=date(2026, 8, 17),
        ends_on=date(2026, 9, 16),
        attendance_calculation_version="attendance-v2",
        actor_user_id=maker.id,
        grants=grants,
    )
    fiscal_year = FiscalYear(
        organization_id=organization.id,
        code="2083-84",
        label="FY 2083/84",
        bs_start_year=2083,
        bs_end_year=2084,
        starts_on=date(2026, 7, 17),
        ends_on=date(2027, 7, 16),
        status="active",
        created_by=maker.id,
        activated_by=checker.id,
    )
    session.add(fiscal_year)
    session.flush()
    session.add(PayrollPeriodContext(period_id=period.id, fiscal_year_id=fiscal_year.id))
    payroll.lock_period(
        organization_id=organization.id,
        period_id=period.id,
        actor_user_id=checker.id,
        grants=grants,
    )
    run = payroll.create_run(
        organization_id=organization.id,
        period_id=period.id,
        calculation_version="payroll-v2",
        policy_snapshot={"test": True},
        actor_user_id=maker.id,
        grants=grants,
    )
    lines = []
    for employee, amount in ((employee_a, "50000"), (employee_b, "60000")):
        lines.append(
            payroll.add_line(
                organization_id=organization.id,
                run_id=run.id,
                employee_id=employee.id,
                gross_amount=amount,
                deduction_amount="0",
                tax_amount="0",
                employee_snapshot={
                    "id": str(employee.id),
                    "employee_code": employee.employee_code,
                    "display_name": employee.display_name,
                },
                attendance_snapshot={"calculation_version": "attendance-v2"},
                earnings_snapshot={"base": amount},
                deductions_snapshot={"items": []},
                explanation={"formula": "gross - deductions - tax"},
                actor_user_id=maker.id,
                grants=grants,
            )
        )
    payroll.submit_run(
        organization_id=organization.id,
        run_id=run.id,
        actor_user_id=maker.id,
        grants=grants,
    )
    payroll.approve_run(
        organization_id=organization.id,
        run_id=run.id,
        actor_user_id=checker.id,
        grants=grants,
    )
    payroll.post_run(
        organization_id=organization.id,
        run_id=run.id,
        actor_user_id=checker.id,
        grants=grants,
    )
    session.commit()
    result = (
        organization.id,
        employee_a.id,
        employee_b.id,
        fiscal_year.id,
        lines[0].id,
        lines[1].id,
    )
    session.close()
    return result


def test_employee_payroll_self_service_never_accepts_foreign_employee_identity() -> None:
    (
        organization_id,
        employee_a_id,
        employee_b_id,
        fiscal_year_id,
        line_a_id,
        line_b_id,
    ) = _seed_posted_payroll()
    assert isinstance(organization_id, UUID)
    with TestClient(create_app()) as client:
        _login(client, "employee.a", "employee-a-password-123")
        payslips = client.get(
            f"/api/v1/organizations/{organization_id}/payroll-v2/self/payslips"
        )
        assert payslips.status_code == 200, payslips.text
        assert len(payslips.json()) == 1
        assert payslips.json()[0]["employee"]["id"] == str(employee_a_id)
        assert payslips.json()[0]["employee"]["id"] != str(employee_b_id)

        own = client.get(
            f"/api/v1/organizations/{organization_id}/payroll-v2/"
            f"self/payslips/{line_a_id}"
        )
        assert own.status_code == 200, own.text
        foreign = client.get(
            f"/api/v1/organizations/{organization_id}/payroll-v2/"
            f"self/payslips/{line_b_id}"
        )
        assert foreign.status_code == 404

        annual = client.get(
            f"/api/v1/organizations/{organization_id}/payroll-v2/"
            f"self/annual-summary/{fiscal_year_id}"
        )
        assert annual.status_code == 200, annual.text
        assert len(annual.json()) == 1
        assert annual.json()[0]["employee_id"] == str(employee_a_id)

        admin_report = client.get(
            f"/api/v1/organizations/{organization_id}/payroll-v2/"
            f"annual-summary/{fiscal_year_id}"
        )
        assert admin_report.status_code == 403
