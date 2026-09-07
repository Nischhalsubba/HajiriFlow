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


def test_payroll_api_requires_scope_locking_checker_and_additive_reversal() -> None:
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
        primary = _create_company(client, system_csrf, "Payroll Tenant")
        other = _create_company(client, system_csrf, "Other Tenant")
        employee_response = client.post(
            f"/api/v1/organizations/{primary['id']}/employees",
            headers={"X-CSRF-Token": system_csrf},
            json={
                "employee_code": "EMP-PAY-1",
                "display_name": "Mina Rai",
                "joined_on": "2026-01-01",
            },
        )
        assert employee_response.status_code == 201, employee_response.text
        employee = employee_response.json()

        _seed_admin(
            username="payroll.maker",
            password="payroll-maker-password-123",
            role_code="payroll_administrator",
            organization_id=primary["id"],
        )
        _seed_admin(
            username="payroll.checker",
            password="payroll-checker-password-123",
            role_code="payroll_administrator",
            organization_id=primary["id"],
        )
        client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": system_csrf},
        )

        maker_csrf = _login(
            client,
            "payroll.maker",
            "payroll-maker-password-123",
        )
        assert client.get(
            f"/api/v1/organizations/{other['id']}/payroll/periods"
        ).status_code == 403

        period_response = client.post(
            f"/api/v1/organizations/{primary['id']}/payroll/periods",
            headers={"X-CSRF-Token": maker_csrf},
            json={
                "code": "2083-05",
                "label": "Bhadra 2083",
                "starts_on": "2026-08-17",
                "ends_on": "2026-09-16",
                "attendance_calculation_version": "attendance-v1",
            },
        )
        assert period_response.status_code == 201, period_response.text
        period = period_response.json()

        maker_lock = client.post(
            f"/api/v1/organizations/{primary['id']}/payroll/periods/"
            f"{period['id']}/lock",
            headers={"X-CSRF-Token": maker_csrf},
        )
        assert maker_lock.status_code == 400
        assert "independent approval" in maker_lock.json()["detail"]

        client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": maker_csrf},
        )
        checker_csrf = _login(
            client,
            "payroll.checker",
            "payroll-checker-password-123",
        )
        locked = client.post(
            f"/api/v1/organizations/{primary['id']}/payroll/periods/"
            f"{period['id']}/lock",
            headers={"X-CSRF-Token": checker_csrf},
        )
        assert locked.status_code == 200, locked.text
        assert locked.json()["status"] == "locked"

        client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": checker_csrf},
        )
        maker_csrf = _login(
            client,
            "payroll.maker",
            "payroll-maker-password-123",
        )
        run_response = client.post(
            f"/api/v1/organizations/{primary['id']}/payroll/runs",
            headers={"X-CSRF-Token": maker_csrf},
            json={
                "period_id": period["id"],
                "calculation_version": "payroll-v1",
                "policy_snapshot": {"policy": "fixture-v1"},
            },
        )
        assert run_response.status_code == 201, run_response.text
        run = run_response.json()

        line_response = client.post(
            f"/api/v1/organizations/{primary['id']}/payroll/runs/"
            f"{run['id']}/lines",
            headers={"X-CSRF-Token": maker_csrf},
            json={
                "employee_id": employee["id"],
                "gross_amount": "100000.00",
                "deduction_amount": "5000.00",
                "tax_amount": "10000.00",
                "employee_snapshot": {"employee_code": employee["employee_code"]},
                "attendance_snapshot": {"calculation_version": "attendance-v1"},
                "earnings_snapshot": {"base": "100000.00"},
                "deductions_snapshot": {"other": "5000.00"},
                "explanation": {"basis": "fixture"},
            },
        )
        assert line_response.status_code == 201, line_response.text
        assert line_response.json()["net_amount"] == "85000.00"

        submitted = client.post(
            f"/api/v1/organizations/{primary['id']}/payroll/runs/"
            f"{run['id']}/submit",
            headers={"X-CSRF-Token": maker_csrf},
        )
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["status"] == "pending_approval"

        self_approval = client.post(
            f"/api/v1/organizations/{primary['id']}/payroll/runs/"
            f"{run['id']}/approve",
            headers={"X-CSRF-Token": maker_csrf},
        )
        assert self_approval.status_code == 400
        assert "maker cannot approve" in self_approval.json()["detail"]

        client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": maker_csrf},
        )
        checker_csrf = _login(
            client,
            "payroll.checker",
            "payroll-checker-password-123",
        )
        approved = client.post(
            f"/api/v1/organizations/{primary['id']}/payroll/runs/"
            f"{run['id']}/approve",
            headers={"X-CSRF-Token": checker_csrf},
        )
        assert approved.status_code == 200, approved.text
        posted = client.post(
            f"/api/v1/organizations/{primary['id']}/payroll/runs/"
            f"{run['id']}/post",
            headers={"X-CSRF-Token": checker_csrf},
        )
        assert posted.status_code == 200, posted.text
        assert posted.json()["status"] == "posted"

        export = client.get(
            f"/api/v1/organizations/{primary['id']}/payroll/runs/"
            f"{run['id']}/export"
        )
        assert export.status_code == 200, export.text
        assert export.json()[0]["net"] == "85000.00"

        client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": checker_csrf},
        )
        maker_csrf = _login(
            client,
            "payroll.maker",
            "payroll-maker-password-123",
        )
        reversal_request = client.post(
            f"/api/v1/organizations/{primary['id']}/payroll/runs/"
            f"{run['id']}/reversal-request",
            headers={"X-CSRF-Token": maker_csrf},
            json={"reason": "Correction required after approved payroll review."},
        )
        assert reversal_request.status_code == 200, reversal_request.text
        assert reversal_request.json()["status"] == "reversal_pending"

        client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": maker_csrf},
        )
        checker_csrf = _login(
            client,
            "payroll.checker",
            "payroll-checker-password-123",
        )
        reversal = client.post(
            f"/api/v1/organizations/{primary['id']}/payroll/runs/"
            f"{run['id']}/reversal-approve",
            headers={"X-CSRF-Token": checker_csrf},
        )
        assert reversal.status_code == 200, reversal.text
        assert reversal.json()["status"] == "posted"
        assert reversal.json()["reversal_of_run_id"] == run["id"]

        original_runs = client.get(
            f"/api/v1/organizations/{primary['id']}/payroll/runs"
        )
        assert original_runs.status_code == 200, original_runs.text
        by_id = {item["id"]: item for item in original_runs.json()}
        assert by_id[run["id"]]["status"] == "reversed"
        assert by_id[run["id"]]["reversal_run_id"] == reversal.json()["id"]

        history = client.get(
            f"/api/v1/organizations/{primary['id']}/payroll/runs/"
            f"{run['id']}/history"
        )
        assert history.status_code == 200, history.text
        actions = [item["action"] for item in history.json()]
        assert actions == [
            "run.created",
            "line.added",
            "run.submitted",
            "run.approved",
            "run.posted",
            "run.exported",
            "reversal.requested",
            "reversal.approved",
        ]
