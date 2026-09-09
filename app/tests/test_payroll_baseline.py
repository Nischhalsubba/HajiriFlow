from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from hajiriflow.db.models.attendance import AttendanceRecord
from hajiriflow.db.models.attendance_baseline import AttendanceRecordDetail
from hajiriflow.db.models.identity import UserAccount
from hajiriflow.db.models.payroll import PayrollLine
from hajiriflow.db.models.payroll_baseline import EarningHead
from hajiriflow.db.models.workforce import CompanyProfile, Employee
from hajiriflow.db.session import get_session_factory
from hajiriflow.identity.permissions import FULL_ACCESS, PermissionGrant
from hajiriflow.payroll.baseline import PayrollBaselineService

pytestmark = pytest.mark.usefixtures("database")


def _full_access() -> frozenset[PermissionGrant]:
    return frozenset({PermissionGrant(FULL_ACCESS)})


def _seed(session):
    organization = CompanyProfile(
        legal_name="Payroll Baseline Pvt. Ltd.",
        display_name="Payroll Baseline",
        timezone="Asia/Kathmandu",
    )
    maker = UserAccount(
        username="baseline.maker",
        password_hash="test-hash",
        display_name="Payroll Maker",
    )
    checker = UserAccount(
        username="baseline.checker",
        password_hash="test-hash",
        display_name="Payroll Checker",
    )
    session.add_all([organization, maker, checker])
    session.flush()
    employee = Employee(
        organization_id=organization.id,
        employee_code="E-100",
        display_name="Reconciliation Employee",
        joined_on=date(2026, 1, 1),
    )
    other = Employee(
        organization_id=organization.id,
        employee_code="E-200",
        display_name="Other Employee",
        joined_on=date(2026, 1, 1),
    )
    session.add_all([employee, other])
    session.flush()
    return organization, employee, other, maker, checker


def _attendance(session, organization, employee, *, work_date=date(2026, 9, 1)):
    record = AttendanceRecord(
        organization_id=organization.id,
        employee_id=employee.id,
        work_date=work_date,
        worked_minutes=480,
        late_minutes=0,
        status="present",
        calculation_version="attendance-v2",
        source_punch_count=2,
    )
    session.add(record)
    session.flush()
    session.add(
        AttendanceRecordDetail(
            attendance_record_id=record.id,
            day_status="present",
            planned_minutes=480,
            break_minutes=0,
            early_arrival_minutes=0,
            early_departure_minutes=0,
            late_departure_minutes=0,
            regular_overtime_minutes=0,
            holiday_overtime_minutes=0,
            duplicate_event_count=0,
            input_fingerprint="a" * 64,
            engine_version="attendance-v2",
            explanation_trace=[{"rule": "test", "decision": "present"}],
        )
    )
    session.flush()
    return record


def _prepare_baseline(session):
    organization, employee, other, maker, checker = _seed(session)
    grants = _full_access()
    service = PayrollBaselineService(session)
    fiscal_year = service.create_fiscal_year(
        organization_id=organization.id,
        code="2083-84",
        label="FY 2083/84",
        bs_start_year=2083,
        bs_end_year=2084,
        starts_on=date(2026, 7, 17),
        ends_on=date(2027, 7, 16),
        actor_user_id=maker.id,
        grants=grants,
    )
    with pytest.raises(ValueError, match="independent approval"):
        service.transition_fiscal_year(
            organization_id=organization.id,
            fiscal_year_id=fiscal_year.id,
            target_status="active",
            actor_user_id=maker.id,
            grants=grants,
        )
    service.transition_fiscal_year(
        organization_id=organization.id,
        fiscal_year_id=fiscal_year.id,
        target_status="active",
        actor_user_id=checker.id,
        grants=grants,
    )
    earning = service.create_earning_head(
        organization_id=organization.id,
        code="ALLOWANCE",
        name="Fixed allowance",
        calculation_type="fixed",
        payment_frequency="monthly",
        taxable=True,
        actor_user_id=maker.id,
        grants=grants,
    )
    deduction = service.create_deduction_type(
        organization_id=organization.id,
        code="PRETAX",
        name="Pretax contribution",
        calculation_type="fixed",
        payment_frequency="monthly",
        pretax=True,
        enrollment_required=False,
        cap_amount=None,
        actor_user_id=maker.id,
        grants=grants,
    )
    profile = service.create_compensation_profile(
        organization_id=organization.id,
        employee_id=employee.id,
        base_salary=Decimal("100000.00"),
        tax_category="resident",
        overtime_eligible=True,
        standard_monthly_minutes=12480,
        starts_on=date(2026, 7, 17),
        ends_on=None,
        actor_user_id=maker.id,
        grants=grants,
    )
    service.add_compensation_component(
        organization_id=organization.id,
        compensation_profile_id=profile.id,
        component_type="earning",
        catalog_id=earning.id,
        value=Decimal("10000.00"),
        actor_user_id=maker.id,
        grants=grants,
    )
    service.add_compensation_component(
        organization_id=organization.id,
        compensation_profile_id=profile.id,
        component_type="deduction",
        catalog_id=deduction.id,
        value=Decimal("5000.00"),
        actor_user_id=maker.id,
        grants=grants,
    )
    tax_policy = service.create_tax_slab_set(
        organization_id=organization.id,
        fiscal_year_id=fiscal_year.id,
        taxpayer_category="resident",
        version="synthetic-v1",
        standard_deduction=Decimal("0"),
        slabs=(
            (Decimal("0"), Decimal("500000"), Decimal("0.01")),
            (Decimal("500000"), Decimal("1000000"), Decimal("0.10")),
            (Decimal("1000000"), None, Decimal("0.20")),
        ),
        actor_user_id=maker.id,
        grants=grants,
    )
    with pytest.raises(ValueError, match="independent approval"):
        service.confirm_tax_slab_set(
            organization_id=organization.id,
            tax_slab_set_id=tax_policy.id,
            actor_user_id=maker.id,
            grants=grants,
        )
    service.confirm_tax_slab_set(
        organization_id=organization.id,
        tax_slab_set_id=tax_policy.id,
        actor_user_id=checker.id,
        grants=grants,
    )
    period = service.create_period(
        organization_id=organization.id,
        fiscal_year_id=fiscal_year.id,
        code="2083-05",
        label="Bhadra 2083",
        starts_on=date(2026, 8, 17),
        ends_on=date(2026, 9, 16),
        attendance_calculation_version="attendance-v2",
        actor_user_id=maker.id,
        grants=grants,
    )
    _attendance(session, organization, employee)
    review = service.prepare_attendance_review(
        organization_id=organization.id,
        period_id=period.id,
        employee_id=employee.id,
        actor_user_id=maker.id,
        grants=grants,
    )
    service.decide_attendance_review(
        organization_id=organization.id,
        review_id=review.id,
        approve=True,
        note="Attendance reconciled against v2 evidence.",
        actor_user_id=checker.id,
        grants=grants,
    )
    service.lifecycle.lock_period(
        organization_id=organization.id,
        period_id=period.id,
        actor_user_id=checker.id,
        grants=grants,
    )
    return (
        service,
        organization,
        employee,
        other,
        maker,
        checker,
        fiscal_year,
        earning,
        period,
        grants,
    )


def test_generation_requires_policy_and_reconciles_exactly_to_paisa() -> None:
    session = get_session_factory()()
    try:
        (
            service,
            organization,
            employee,
            _other,
            maker,
            _checker,
            fiscal_year,
            _earning,
            period,
            grants,
        ) = _prepare_baseline(session)
        preview = service.preview_employee(
            organization_id=organization.id,
            period_id=period.id,
            employee_id=employee.id,
        )
        assert preview["gross"] == "110000.00"
        assert preview["deduction_total"] == "5000.00"
        assert preview["taxable_period_income"] == "105000.00"
        assert preview["projected_annual_taxable_income"] == "1260000.00"
        assert preview["projected_annual_tax"] == "107000.00"
        assert preview["tax"] == "8916.67"
        assert preview["net"] == "96083.33"

        projection = service.tax_projection(
            organization_id=organization.id,
            fiscal_year_id=fiscal_year.id,
            employee_id=employee.id,
            projected_taxable_income=Decimal("1260000"),
        )
        assert projection["projected_tax"] == "107000.00"

        run = service.generate_run(
            organization_id=organization.id,
            period_id=period.id,
            employee_ids=(employee.id,),
            calculation_version="payroll-v2",
            actor_user_id=maker.id,
            grants=grants,
        )
        line = session.scalar(select(PayrollLine).where(PayrollLine.run_id == run.id))
        assert line is not None
        assert line.gross_amount == Decimal("110000.00")
        assert line.deduction_amount == Decimal("5000.00")
        assert line.tax_amount == Decimal("8916.67")
        assert line.net_amount == Decimal("96083.33")
        assert line.attendance_snapshot["calculation_version"] == "attendance-v2"
        assert line.deductions_snapshot["tax_policy"]["version"] == "synthetic-v1"
    finally:
        session.close()


def test_posted_payslip_is_snapshot_stable_and_reversal_reconciles() -> None:
    session = get_session_factory()()
    try:
        (
            service,
            organization,
            employee,
            _other,
            maker,
            checker,
            fiscal_year,
            earning,
            period,
            grants,
        ) = _prepare_baseline(session)
        run = service.generate_run(
            organization_id=organization.id,
            period_id=period.id,
            employee_ids=(employee.id,),
            calculation_version="payroll-v2",
            actor_user_id=maker.id,
            grants=grants,
        )
        line = session.scalar(select(PayrollLine).where(PayrollLine.run_id == run.id))
        assert line is not None
        service.lifecycle.submit_run(
            organization_id=organization.id,
            run_id=run.id,
            actor_user_id=maker.id,
            grants=grants,
        )
        service.lifecycle.approve_run(
            organization_id=organization.id,
            run_id=run.id,
            actor_user_id=checker.id,
            grants=grants,
        )
        service.lifecycle.post_run(
            organization_id=organization.id,
            run_id=run.id,
            actor_user_id=checker.id,
            grants=grants,
        )
        before = service.payslip_payload(
            organization_id=organization.id,
            line_id=line.id,
        )
        earning.name = "Changed current catalog name"
        earning.taxable = False
        session.flush()
        after = service.payslip_payload(
            organization_id=organization.id,
            line_id=line.id,
        )
        assert after == before
        assert service.payslip_pdf(
            organization_id=organization.id,
            line_id=line.id,
        ).startswith(b"%PDF-1.4")

        summary = service.annual_summary(
            organization_id=organization.id,
            fiscal_year_id=fiscal_year.id,
            employee_id=employee.id,
        )
        assert summary[0]["net"] == "96083.33"
        assert service.annual_summary_xlsx(
            organization_id=organization.id,
            fiscal_year_id=fiscal_year.id,
        ).startswith(b"PK")

        service.lifecycle.request_reversal(
            organization_id=organization.id,
            run_id=run.id,
            actor_user_id=maker.id,
            reason="Approved compensation input was incorrect.",
            grants=grants,
        )
        service.lifecycle.approve_reversal(
            organization_id=organization.id,
            run_id=run.id,
            actor_user_id=checker.id,
            grants=grants,
        )
        reversed_summary = service.annual_summary(
            organization_id=organization.id,
            fiscal_year_id=fiscal_year.id,
            employee_id=employee.id,
        )
        assert reversed_summary[0]["gross"] == "0.00"
        assert reversed_summary[0]["tax"] == "0.00"
        assert reversed_summary[0]["net"] == "0.00"
    finally:
        session.close()


def test_generation_fails_without_approved_attendance_or_confirmed_tax() -> None:
    session = get_session_factory()()
    try:
        organization, employee, _other, maker, checker = _seed(session)
        service = PayrollBaselineService(session)
        grants = _full_access()
        fiscal_year = service.create_fiscal_year(
            organization_id=organization.id,
            code="2083-84",
            label="FY 2083/84",
            bs_start_year=2083,
            bs_end_year=2084,
            starts_on=date(2026, 7, 17),
            ends_on=date(2027, 7, 16),
            actor_user_id=maker.id,
            grants=grants,
        )
        service.transition_fiscal_year(
            organization_id=organization.id,
            fiscal_year_id=fiscal_year.id,
            target_status="active",
            actor_user_id=checker.id,
            grants=grants,
        )
        service.create_compensation_profile(
            organization_id=organization.id,
            employee_id=employee.id,
            base_salary=Decimal("100000"),
            tax_category="resident",
            overtime_eligible=False,
            standard_monthly_minutes=12480,
            starts_on=date(2026, 7, 17),
            ends_on=None,
            actor_user_id=maker.id,
            grants=grants,
        )
        period = service.create_period(
            organization_id=organization.id,
            fiscal_year_id=fiscal_year.id,
            code="2083-05",
            label="Bhadra 2083",
            starts_on=date(2026, 8, 17),
            ends_on=date(2026, 9, 16),
            attendance_calculation_version="attendance-v2",
            actor_user_id=maker.id,
            grants=grants,
        )
        service.lifecycle.lock_period(
            organization_id=organization.id,
            period_id=period.id,
            actor_user_id=checker.id,
            grants=grants,
        )
        with pytest.raises(ValueError, match="approved attendance review"):
            service.generate_run(
                organization_id=organization.id,
                period_id=period.id,
                employee_ids=(employee.id,),
                calculation_version="payroll-v2",
                actor_user_id=maker.id,
                grants=grants,
            )
    finally:
        session.close()
