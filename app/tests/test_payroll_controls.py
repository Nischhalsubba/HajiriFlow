from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from hajiriflow.db.models.identity import UserAccount
from hajiriflow.db.models.payroll import PayrollHistory, PayrollLine, PayrollRun
from hajiriflow.db.models.workforce import CompanyProfile, Employee
from hajiriflow.db.session import get_session_factory
from hajiriflow.identity.permissions import FULL_ACCESS, PermissionGrant, ScopeType
from hajiriflow.payroll.service import PAYROLL_MANAGE, PayrollService


def _full_access() -> frozenset[PermissionGrant]:
    return frozenset({PermissionGrant(FULL_ACCESS)})


def _seed(session):
    organization = CompanyProfile(
        legal_name="Acme Pvt Ltd",
        display_name="Acme",
        timezone="Asia/Kathmandu",
    )
    other_organization = CompanyProfile(
        legal_name="Other Pvt Ltd",
        display_name="Other",
        timezone="Asia/Kathmandu",
    )
    maker = UserAccount(
        username="payroll.maker",
        password_hash="test-hash",
        display_name="Payroll Maker",
    )
    checker = UserAccount(
        username="payroll.checker",
        password_hash="test-hash",
        display_name="Payroll Checker",
    )
    session.add_all([organization, other_organization, maker, checker])
    session.flush()
    employee = Employee(
        organization_id=organization.id,
        employee_code="E-001",
        display_name="Employee One",
        joined_on=date(2026, 1, 1),
    )
    session.add(employee)
    session.flush()
    return organization, other_organization, employee, maker, checker


def _build_posted_run(session):
    organization, other_organization, employee, maker, checker = _seed(session)
    grants = _full_access()
    service = PayrollService(session)
    period = service.create_period(
        organization_id=organization.id,
        code="2083-05",
        label="Bhadra 2083",
        starts_on=date(2026, 8, 17),
        ends_on=date(2026, 9, 16),
        attendance_calculation_version="attendance-v1",
        actor_user_id=maker.id,
        grants=grants,
    )
    with pytest.raises(ValueError, match="independent approval"):
        service.lock_period(
            organization_id=organization.id,
            period_id=period.id,
            actor_user_id=maker.id,
            grants=grants,
        )
    service.lock_period(
        organization_id=organization.id,
        period_id=period.id,
        actor_user_id=checker.id,
        grants=grants,
    )
    run = service.create_run(
        organization_id=organization.id,
        period_id=period.id,
        calculation_version="payroll-2026.09",
        policy_snapshot={"tax_slab_version": "2083-v1", "overtime_multiplier": "1.5"},
        actor_user_id=maker.id,
        grants=grants,
    )
    line = service.add_line(
        organization_id=organization.id,
        run_id=run.id,
        employee_id=employee.id,
        gross_amount="100000.00",
        deduction_amount="5000.00",
        tax_amount="10000.00",
        employee_snapshot={"employee_code": employee.employee_code},
        attendance_snapshot={"present_days": 22, "version": "attendance-v1"},
        earnings_snapshot={"base": "100000.00"},
        deductions_snapshot={"provident_fund": "5000.00"},
        explanation={"formula": "gross - deductions - tax"},
        actor_user_id=maker.id,
        grants=grants,
    )
    assert line.net_amount == Decimal("85000.00")
    service.submit_run(
        organization_id=organization.id,
        run_id=run.id,
        actor_user_id=maker.id,
        grants=grants,
    )
    with pytest.raises(ValueError, match="maker cannot approve"):
        service.approve_run(
            organization_id=organization.id,
            run_id=run.id,
            actor_user_id=maker.id,
            grants=grants,
        )
    service.approve_run(
        organization_id=organization.id,
        run_id=run.id,
        actor_user_id=checker.id,
        grants=grants,
    )
    service.post_run(
        organization_id=organization.id,
        run_id=run.id,
        actor_user_id=checker.id,
        grants=grants,
    )
    return (
        service,
        organization,
        other_organization,
        employee,
        maker,
        checker,
        period,
        run,
    )


def test_payroll_requires_locked_period_and_independent_approval(database) -> None:
    del database
    session = get_session_factory()()
    try:
        (
            _service,
            _organization,
            _other_organization,
            _employee,
            _maker,
            checker,
            period,
            run,
        ) = _build_posted_run(session)
        assert period.status == "locked"
        assert period.locked_by == checker.id
        assert run.status == "posted"
        assert run.approved_by == checker.id
        assert run.posted_by == checker.id
        assert run.calculation_version == "payroll-2026.09"
    finally:
        session.close()


def test_payroll_export_is_permission_and_state_gated(database) -> None:
    del database
    session = get_session_factory()()
    try:
        service, organization, _, _, maker, _, _, run = _build_posted_run(session)
        manage_only = frozenset(
            {
                PermissionGrant(
                    PAYROLL_MANAGE,
                    scope_type=ScopeType.ORGANIZATION,
                    scope_id=organization.id,
                )
            }
        )
        with pytest.raises(PermissionError, match="payroll.export"):
            service.export_rows(
                organization_id=organization.id,
                run_id=run.id,
                actor_user_id=maker.id,
                grants=manage_only,
            )
        rows = service.export_rows(
            organization_id=organization.id,
            run_id=run.id,
            actor_user_id=maker.id,
            grants=_full_access(),
        )
        assert rows == [
            {
                "employee_id": rows[0]["employee_id"],
                "direction": "payroll",
                "currency": "NPR",
                "gross": "100000.00",
                "deductions": "5000.00",
                "tax": "10000.00",
                "net": "85000.00",
            }
        ]
    finally:
        session.close()


def test_payroll_reversal_is_additive_and_requires_second_approver(database) -> None:
    del database
    session = get_session_factory()()
    try:
        service, organization, _, employee, maker, checker, period, run = _build_posted_run(session)
        service.request_reversal(
            organization_id=organization.id,
            run_id=run.id,
            actor_user_id=maker.id,
            reason="Incorrect approved compensation input.",
            grants=_full_access(),
        )
        with pytest.raises(ValueError, match="independent approval"):
            service.approve_reversal(
                organization_id=organization.id,
                run_id=run.id,
                actor_user_id=maker.id,
                grants=_full_access(),
            )
        reversal = service.approve_reversal(
            organization_id=organization.id,
            run_id=run.id,
            actor_user_id=checker.id,
            grants=_full_access(),
        )
        assert run.status == "reversed"
        assert run.reversal_run_id == reversal.id
        assert reversal.status == "posted"
        assert reversal.reversal_of_run_id == run.id
        reversal_line = session.scalar(
            select(PayrollLine).where(PayrollLine.run_id == reversal.id)
        )
        assert reversal_line is not None
        assert reversal_line.employee_id == employee.id
        assert reversal_line.direction == "reversal"
        assert reversal_line.net_amount == Decimal("85000.00")

        service.close_period(
            organization_id=organization.id,
            period_id=period.id,
            actor_user_id=checker.id,
            grants=_full_access(),
        )
        assert period.status == "closed"
        assert session.scalar(select(func.count(PayrollRun.id))) == 2
    finally:
        session.close()


def test_payroll_permission_scope_is_organization_bound(database) -> None:
    del database
    session = get_session_factory()()
    try:
        organization, other_organization, _employee, maker, _checker = _seed(session)
        grants = frozenset(
            {
                PermissionGrant(
                    PAYROLL_MANAGE,
                    scope_type=ScopeType.ORGANIZATION,
                    scope_id=organization.id,
                )
            }
        )
        with pytest.raises(PermissionError, match="payroll.manage"):
            PayrollService(session).create_period(
                organization_id=other_organization.id,
                code="2083-05",
                label="Bhadra 2083",
                starts_on=date(2026, 8, 17),
                ends_on=date(2026, 9, 16),
                attendance_calculation_version="attendance-v1",
                actor_user_id=maker.id,
                grants=grants,
            )
    finally:
        session.close()


def test_payroll_history_is_immutable(database) -> None:
    del database
    session = get_session_factory()()
    try:
        _build_posted_run(session)
        history = session.scalar(select(PayrollHistory))
        assert history is not None
        history.reason = "tampered"
        with pytest.raises(RuntimeError, match="immutable"):
            session.flush()
        session.rollback()
    finally:
        session.close()
