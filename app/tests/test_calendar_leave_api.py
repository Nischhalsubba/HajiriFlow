from decimal import Decimal
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


def seed_users() -> tuple[UUID, UUID, UUID]:
    session = get_session_factory()()
    seed_identity_catalog(session)
    service = IdentityService(session, get_settings())
    system_admin = service.create_user(
        username="system.admin",
        display_name="System Admin",
        password="system-admin-password-123",
        must_change_password=False,
    )
    workforce_admin = service.create_user(
        username="workforce.admin",
        display_name="Workforce Admin",
        password="workforce-admin-password-123",
        must_change_password=False,
    )
    employee = service.create_user(
        username="employee.one",
        display_name="Employee One",
        password="employee-one-password-123",
        must_change_password=False,
    )
    service.assign_role(
        user_id=system_admin.id,
        role_code="system_administrator",
        actor_user_id=system_admin.id,
        scope_type=ScopeType.GLOBAL,
    )
    session.commit()
    ids = (system_admin.id, workforce_admin.id, employee.id)
    session.close()
    return ids


def login(client: TestClient, username: str, password: str) -> tuple[str, dict]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"], response.json()["user"]


def create_company(client: TestClient, csrf: str, name: str) -> dict:
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


def assign_scoped_roles(
    organization_id: str,
    *,
    system_admin_id: UUID,
    workforce_admin_id: UUID,
    employee_user_id: UUID,
) -> None:
    session = get_session_factory()()
    service = IdentityService(session, get_settings())
    scope_id = UUID(organization_id)
    service.assign_role(
        user_id=workforce_admin_id,
        role_code="workforce_administrator",
        actor_user_id=system_admin_id,
        scope_type=ScopeType.ORGANIZATION,
        scope_id=scope_id,
    )
    service.assign_role(
        user_id=employee_user_id,
        role_code="employee",
        actor_user_id=system_admin_id,
        scope_type=ScopeType.ORGANIZATION,
        scope_id=scope_id,
    )
    session.commit()
    session.close()


def test_bs_roundtrip_and_month_metadata_use_one_calendar_service() -> None:
    seed_users()
    with TestClient(create_app()) as client:
        login(client, "system.admin", "system-admin-password-123")

        ad_to_bs = client.get(
            "/api/v1/calendar/convert",
            params={"ad_date": "2024-02-12"},
        )
        assert ad_to_bs.status_code == 200, ad_to_bs.text
        assert ad_to_bs.json() == {
            "ad_date": "2024-02-12",
            "bs_date": "2080-10-29",
        }

        bs_to_ad = client.get(
            "/api/v1/calendar/convert",
            params={"bs_date": "2080-10-29"},
        )
        assert bs_to_ad.status_code == 200, bs_to_ad.text
        assert bs_to_ad.json()["ad_date"] == "2024-02-12"

        metadata = client.get("/api/v1/calendar/bs-month/2080/10")
        assert metadata.status_code == 200, metadata.text
        assert metadata.json()["days"] in {29, 30, 31, 32}
        assert metadata.json()["first_ad_date"] <= "2024-02-12"
        assert metadata.json()["last_ad_date"] >= "2024-02-12"


def test_leave_and_field_duty_share_deterministic_workday_rules() -> None:
    system_admin_id, workforce_admin_id, employee_user_id = seed_users()
    with TestClient(create_app()) as client:
        system_csrf, _ = login(client, "system.admin", "system-admin-password-123")
        primary = create_company(client, system_csrf, "HajiriFlow Nepal")
        other = create_company(client, system_csrf, "Other Tenant")
        assign_scoped_roles(
            primary["id"],
            system_admin_id=system_admin_id,
            workforce_admin_id=workforce_admin_id,
            employee_user_id=employee_user_id,
        )

        employee_response = client.post(
            f"/api/v1/organizations/{primary['id']}/employees",
            headers={"X-CSRF-Token": system_csrf},
            json={
                "employee_code": "EMP-001",
                "display_name": "Employee One",
                "joined_on": "2026-01-01",
                "user_account_id": str(employee_user_id),
            },
        )
        assert employee_response.status_code == 201, employee_response.text
        employee_id = employee_response.json()["id"]

        workforce_csrf, _ = login(
            client,
            "workforce.admin",
            "workforce-admin-password-123",
        )
        holiday_response = client.post(
            f"/api/v1/organizations/{primary['id']}/holidays",
            headers={"X-CSRF-Token": workforce_csrf},
            json={
                "holiday_date": "2026-09-07",
                "name": "Organization Holiday",
                "category": "organization",
                "paid": True,
            },
        )
        assert holiday_response.status_code == 201, holiday_response.text

        saturday = client.get(
            f"/api/v1/organizations/{primary['id']}/workday/2026-09-05"
        )
        assert saturday.status_code == 200, saturday.text
        assert saturday.json()["reason"] == "weekend"
        assert saturday.json()["attendance_expected"] is False

        holiday = client.get(
            f"/api/v1/organizations/{primary['id']}/workday/2026-09-07"
        )
        assert holiday.status_code == 200, holiday.text
        assert holiday.json()["reason"] == "holiday"

        policy_response = client.post(
            f"/api/v1/organizations/{primary['id']}/leave/policies",
            headers={"X-CSRF-Token": workforce_csrf},
            json={
                "code": "ANNUAL",
                "name": "Annual Leave",
                "paid": True,
                "half_day_allowed": True,
                "annual_entitlement": "10.00",
            },
        )
        assert policy_response.status_code == 201, policy_response.text
        policy_id = policy_response.json()["id"]

        allocation = client.put(
            f"/api/v1/organizations/{primary['id']}/leave/allocations",
            headers={"X-CSRF-Token": workforce_csrf},
            json={
                "employee_id": employee_id,
                "leave_policy_id": policy_id,
                "period_year": 2083,
                "allocated_days": "10.00",
                "carried_days": "0.00",
                "adjustment_days": "0.00",
            },
        )
        assert allocation.status_code == 200, allocation.text

        employee_csrf, employee_session = login(
            client,
            "employee.one",
            "employee-one-password-123",
        )
        assert employee_session["employee_id"] == employee_id
        assert (
            client.get(
                f"/api/v1/organizations/{other['id']}/calendar/settings"
            ).status_code
            == 403
        )

        leave = client.post(
            f"/api/v1/organizations/{primary['id']}/self/leave/requests",
            headers={"X-CSRF-Token": employee_csrf},
            json={
                "leave_policy_id": policy_id,
                "start_date": "2026-09-04",
                "end_date": "2026-09-08",
                "day_part": "full",
                "reason": "Family commitment",
            },
        )
        assert leave.status_code == 201, leave.text
        assert Decimal(leave.json()["requested_days"]) == Decimal("3.00")
        leave_id = leave.json()["id"]

        balance = client.get(
            f"/api/v1/organizations/{primary['id']}/self/leave/balance/"
            f"{policy_id}/2083"
        )
        assert balance.status_code == 200, balance.text
        assert Decimal(balance.json()["pending"]) == Decimal("3.00")
        assert Decimal(balance.json()["available"]) == Decimal("7.00")

        half_day = client.post(
            f"/api/v1/organizations/{primary['id']}/self/leave/requests",
            headers={"X-CSRF-Token": employee_csrf},
            json={
                "leave_policy_id": policy_id,
                "start_date": "2026-09-09",
                "end_date": "2026-09-09",
                "day_part": "first_half",
                "reason": "Appointment",
            },
        )
        assert half_day.status_code == 201, half_day.text
        assert Decimal(half_day.json()["requested_days"]) == Decimal("0.50")

        saturday_half_day = client.post(
            f"/api/v1/organizations/{primary['id']}/self/leave/requests",
            headers={"X-CSRF-Token": employee_csrf},
            json={
                "leave_policy_id": policy_id,
                "start_date": "2026-09-12",
                "end_date": "2026-09-12",
                "day_part": "second_half",
                "reason": "Invalid weekend request",
            },
        )
        assert saturday_half_day.status_code == 400
        assert "working day" in saturday_half_day.json()["detail"]

        workforce_csrf, _ = login(
            client,
            "workforce.admin",
            "workforce-admin-password-123",
        )
        approved = client.post(
            f"/api/v1/organizations/{primary['id']}/leave/requests/"
            f"{leave_id}/decision",
            headers={"X-CSRF-Token": workforce_csrf},
            json={"decision": "approved", "note": "Approved"},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"

        leave_day = client.get(
            f"/api/v1/organizations/{primary['id']}/workday/2026-09-08",
            params={"employee_id": employee_id},
        )
        assert leave_day.status_code == 200, leave_day.text
        assert leave_day.json()["reason"] == "leave"
        assert leave_day.json()["attendance_expected"] is False
        assert leave_day.json()["counts_as_present"] is False

        employee_csrf, _ = login(
            client,
            "employee.one",
            "employee-one-password-123",
        )
        field_duty = client.post(
            f"/api/v1/organizations/{primary['id']}/self/field-duty/requests",
            headers={"X-CSRF-Token": employee_csrf},
            json={
                "start_date": "2026-09-10",
                "end_date": "2026-09-10",
                "paid": True,
                "reason": "Client site visit",
            },
        )
        assert field_duty.status_code == 201, field_duty.text
        field_duty_id = field_duty.json()["id"]

        overlapping_leave = client.post(
            f"/api/v1/organizations/{primary['id']}/self/leave/requests",
            headers={"X-CSRF-Token": employee_csrf},
            json={
                "leave_policy_id": policy_id,
                "start_date": "2026-09-10",
                "end_date": "2026-09-10",
                "day_part": "full",
                "reason": "Should conflict with field duty",
            },
        )
        assert overlapping_leave.status_code == 400
        assert "field duty" in overlapping_leave.json()["detail"]

        workforce_csrf, _ = login(
            client,
            "workforce.admin",
            "workforce-admin-password-123",
        )
        field_approved = client.post(
            f"/api/v1/organizations/{primary['id']}/field-duty/requests/"
            f"{field_duty_id}/decision",
            headers={"X-CSRF-Token": workforce_csrf},
            json={"decision": "approved", "note": "Approved"},
        )
        assert field_approved.status_code == 200, field_approved.text

        field_day = client.get(
            f"/api/v1/organizations/{primary['id']}/workday/2026-09-10",
            params={"employee_id": employee_id},
        )
        assert field_day.status_code == 200, field_day.text
        assert field_day.json()["reason"] == "field_duty"
        assert field_day.json()["attendance_expected"] is False
        assert field_day.json()["counts_as_present"] is True
