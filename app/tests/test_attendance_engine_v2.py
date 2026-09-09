import io
from datetime import UTC, date, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from openpyxl import Workbook
from sqlalchemy import select

from hajiriflow.attendance.engine import AttendanceEngineService
from hajiriflow.attendance.manual import ManualAttendanceService
from hajiriflow.db.models.attendance_baseline import (
    AttendanceDayRemark,
    AttendanceImportRow,
    AttendanceRecordDetail,
    ManualAttendanceEvent,
)
from hajiriflow.db.models.calendar_leave import Holiday, LeavePolicy, LeaveRequest
from hajiriflow.db.models.device import Device, DeviceEmployeeMapping, DeviceUser
from hajiriflow.db.models.workforce import CompanyProfile, Employee, Shift
from hajiriflow.db.session import get_session_factory
from hajiriflow.device_platform.adapters import DeviceUserRecord, PunchRecord
from hajiriflow.device_platform.service import DevicePlatformService

pytestmark = pytest.mark.usefixtures("database")
NEPAL = ZoneInfo("Asia/Kathmandu")


def _company(session) -> CompanyProfile:
    company = CompanyProfile(
        legal_name="Attendance Engine Pvt. Ltd.",
        display_name="Attendance Engine",
        timezone="Asia/Kathmandu",
    )
    session.add(company)
    session.flush()
    return company


def _employee(session, company: CompanyProfile, code: str = "EMP-001") -> Employee:
    employee = Employee(
        organization_id=company.id,
        employee_code=code,
        display_name=code,
        joined_on=date(2026, 1, 1),
    )
    session.add(employee)
    session.flush()
    return employee


def _shift(session, company: CompanyProfile) -> Shift:
    shift = Shift(
        organization_id=company.id,
        code="NIGHT",
        name="Night shift",
        starts_at=datetime.strptime("22:00", "%H:%M").time(),
        ends_at=datetime.strptime("06:00", "%H:%M").time(),
        break_minutes=60,
        grace_minutes=10,
        status="active",
    )
    session.add(shift)
    session.flush()
    return shift


def _device_with_mapping(session, company: CompanyProfile, employee: Employee) -> Device:
    device = Device(
        organization_id=company.id,
        code="GATE-1",
        name="Main Gate",
        vendor="Gateway",
        adapter_key="hajiriflow_gateway_v1",
        endpoint_uri="http://gateway.internal",
        capabilities={"pull_punches": True, "list_users": True},
        pull_interval_seconds=300,
    )
    session.add(device)
    session.flush()
    DevicePlatformService(session).sync_device_users(
        device=device,
        users=(DeviceUserRecord(external_user_id="42", display_name="EMP-001"),),
    )
    device_user = session.scalar(
        select(DeviceUser).where(
            DeviceUser.device_id == device.id,
            DeviceUser.external_user_id == "42",
        )
    )
    assert device_user is not None
    session.add(
        DeviceEmployeeMapping(
            organization_id=company.id,
            employee_id=employee.id,
            device_user_id=device_user.id,
            status="active",
        )
    )
    session.flush()
    return device


def _ingest(session, device: Device, *, event_id: str, local_time: datetime, kind: str) -> None:
    DevicePlatformService(session).ingest_punches(
        device=device,
        punches=(
            PunchRecord(
                external_event_id=event_id,
                device_user_identifier="42",
                occurred_at=local_time.astimezone(UTC),
                punch_kind=kind,
                evidence={"sequence": event_id},
            ),
        ),
        pull_session=None,
    )


def test_engine_handles_overnight_shift_duplicates_and_is_idempotent(monkeypatch) -> None:
    session = get_session_factory()()
    try:
        company = _company(session)
        employee = _employee(session, company)
        shift = _shift(session, company)
        device = _device_with_mapping(session, company, employee)
        _ingest(
            session,
            device,
            event_id="in-1",
            local_time=datetime(2026, 9, 9, 21, 55, tzinfo=NEPAL),
            kind="in",
        )
        _ingest(
            session,
            device,
            event_id="in-duplicate",
            local_time=datetime(2026, 9, 9, 21, 56, tzinfo=NEPAL),
            kind="in",
        )
        _ingest(
            session,
            device,
            event_id="out-1",
            local_time=datetime(2026, 9, 10, 6, 30, tzinfo=NEPAL),
            kind="out",
        )
        engine = AttendanceEngineService(session)
        monkeypatch.setattr(engine, "_resolve_shift", lambda **_kwargs: shift)

        record = engine.calculate_day(
            organization_id=company.id,
            employee_id=employee.id,
            work_date=date(2026, 9, 9),
            actor_user_id=None,
        )
        detail = session.get(AttendanceRecordDetail, record.id)
        assert detail is not None
        assert record.status == "present"
        assert record.check_in_at.astimezone(NEPAL).date() == date(2026, 9, 9)
        assert record.check_out_at.astimezone(NEPAL).date() == date(2026, 9, 10)
        assert record.worked_minutes == 455
        assert record.late_minutes == 0
        assert record.source_punch_count == 3
        assert detail.day_status == "present"
        assert detail.planned_minutes == 420
        assert detail.break_minutes == 60
        assert detail.early_arrival_minutes == 5
        assert detail.late_departure_minutes == 30
        assert detail.regular_overtime_minutes == 35
        assert detail.holiday_overtime_minutes == 0
        assert detail.duplicate_event_count == 1
        fingerprint = detail.input_fingerprint
        revision = record.source_revision

        same = engine.calculate_day(
            organization_id=company.id,
            employee_id=employee.id,
            work_date=date(2026, 9, 9),
            actor_user_id=None,
        )
        same_detail = session.get(AttendanceRecordDetail, same.id)
        assert same.id == record.id
        assert same.source_revision == revision
        assert same_detail.input_fingerprint == fingerprint
        assert same_detail.explanation_trace == detail.explanation_trace
    finally:
        session.close()


def test_engine_applies_leave_and_holiday_priority_without_erasing_punches() -> None:
    session = get_session_factory()()
    try:
        company = _company(session)
        employee = _employee(session, company)
        device = _device_with_mapping(session, company, employee)
        _ingest(
            session,
            device,
            event_id="holiday-in",
            local_time=datetime(2026, 9, 10, 9, 0, tzinfo=NEPAL),
            kind="in",
        )
        _ingest(
            session,
            device,
            event_id="holiday-out",
            local_time=datetime(2026, 9, 10, 17, 0, tzinfo=NEPAL),
            kind="out",
        )
        session.add(
            Holiday(
                organization_id=company.id,
                holiday_date=date(2026, 9, 10),
                name="Public holiday",
                category="public",
                paid=True,
                status="active",
            )
        )
        engine = AttendanceEngineService(session)
        record = engine.calculate_day(
            organization_id=company.id,
            employee_id=employee.id,
            work_date=date(2026, 9, 10),
        )
        detail = session.get(AttendanceRecordDetail, record.id)
        assert detail is not None
        assert detail.day_status == "holiday"
        assert detail.holiday_overtime_minutes == 480
        assert record.source_punch_count == 2

        policy = LeavePolicy(
            organization_id=company.id,
            code="ANNUAL",
            name="Annual",
            paid=True,
            half_day_allowed=True,
            annual_entitlement=10,
            active=True,
        )
        session.add(policy)
        session.flush()
        session.add(
            LeaveRequest(
                organization_id=company.id,
                employee_id=employee.id,
                leave_policy_id=policy.id,
                start_date=date(2026, 9, 11),
                end_date=date(2026, 9, 11),
                day_part="full",
                requested_days=1,
                status="approved",
                reason="Approved leave",
                requested_by=uuid4(),
                decided_by=None,
            )
        )
        leave_record = engine.calculate_day(
            organization_id=company.id,
            employee_id=employee.id,
            work_date=date(2026, 9, 11),
        )
        leave_detail = session.get(AttendanceRecordDetail, leave_record.id)
        assert leave_detail is not None
        assert leave_detail.day_status == "leave"
        assert any(item["rule"] == "leave" for item in leave_detail.explanation_trace)
    finally:
        session.close()


def test_manual_events_are_approved_reversible_and_respect_period_locks() -> None:
    session = get_session_factory()()
    try:
        company = _company(session)
        employee = _employee(session, company)
        requester = uuid4()
        approver = uuid4()
        service = ManualAttendanceService(session)
        event = service.request_event(
            organization_id=company.id,
            employee_id=employee.id,
            event_time=datetime(2026, 9, 9, 9, 0, tzinfo=NEPAL),
            event_type="in",
            reason="Missing device punch",
            evidence_note="Supervisor verified",
            requested_by=requester,
        )
        assert event.status == "pending"
        with pytest.raises(ValueError, match="independent approval"):
            service.decide_event(
                organization_id=company.id,
                event_id=event.id,
                approve=True,
                decision_reason="self approve",
                decided_by=requester,
            )
        approved = service.decide_event(
            organization_id=company.id,
            event_id=event.id,
            approve=True,
            decision_reason="verified",
            decided_by=approver,
        )
        assert approved.status == "approved"

        lock = service.lock_period(
            organization_id=company.id,
            starts_on=date(2026, 9, 9),
            ends_on=date(2026, 9, 9),
            reason="Payroll review",
            locked_by=approver,
        )
        engine = AttendanceEngineService(session)
        with pytest.raises(ValueError, match="period is locked"):
            engine.calculate_day(
                organization_id=company.id,
                employee_id=employee.id,
                work_date=date(2026, 9, 9),
            )
        with pytest.raises(ValueError, match="period is locked"):
            service.revoke_event(
                organization_id=company.id,
                event_id=event.id,
                reason="incorrect evidence",
                actor_user_id=approver,
            )
        service.reopen_period(
            organization_id=company.id,
            lock_id=lock.id,
            reason="authorized correction",
            reopened_by=approver,
        )
        revoked = service.revoke_event(
            organization_id=company.id,
            event_id=event.id,
            reason="incorrect evidence",
            actor_user_id=approver,
        )
        assert revoked.status == "revoked"
        record = engine.calculate_day(
            organization_id=company.id,
            employee_id=employee.id,
            work_date=date(2026, 9, 9),
        )
        assert record.status == "absent"
    finally:
        session.close()


def _workbook_bytes(rows: list[tuple]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Manual attendance"
    sheet.append(("employee_code", "event_time", "event_type", "reason", "evidence_note"))
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_spreadsheet_import_previews_rows_and_applies_valid_rows_only() -> None:
    session = get_session_factory()()
    try:
        company = _company(session)
        _employee(session, company, code="EMP-001")
        requester = uuid4()
        approver = uuid4()
        content = _workbook_bytes(
            [
                (
                    "EMP-001",
                    datetime(2026, 9, 9, 9, 0),
                    "in",
                    "Approved missing punch",
                    "Supervisor verified",
                ),
                (
                    "UNKNOWN",
                    datetime(2026, 9, 9, 10, 0),
                    "out",
                    "Invalid employee",
                    None,
                ),
            ]
        )
        service = ManualAttendanceService(session)
        preview = service.preview_import(
            organization_id=company.id,
            filename="attendance.xlsx",
            content=content,
            strict_mode=False,
            requested_by=requester,
        )
        assert preview.total_rows == 2
        assert preview.valid_rows == 1
        assert preview.invalid_rows == 1
        same = service.preview_import(
            organization_id=company.id,
            filename="attendance.xlsx",
            content=content,
            strict_mode=False,
            requested_by=requester,
        )
        assert same.id == preview.id
        rows = session.scalars(
            select(AttendanceImportRow)
            .where(AttendanceImportRow.session_id == preview.id)
            .order_by(AttendanceImportRow.row_number)
        ).all()
        assert rows[0].is_valid is True
        assert rows[1].errors == ["unknown_employee_code"]

        applied = service.apply_import(
            organization_id=company.id,
            import_session_id=preview.id,
            approved_by=approver,
        )
        assert applied.status == "applied"
        assert applied.applied_rows == 1
        events = session.scalars(select(ManualAttendanceEvent)).all()
        assert len(events) == 1
        assert events[0].status == "approved"
        assert events[0].import_session_id == preview.id
    finally:
        session.close()


def test_day_remarks_are_append_only() -> None:
    session = get_session_factory()()
    try:
        company = _company(session)
        employee = _employee(session, company)
        service = ManualAttendanceService(session)
        remark = service.add_remark(
            organization_id=company.id,
            employee_id=employee.id,
            work_date=date(2026, 9, 9),
            remark="Reviewed with supervisor",
            created_by=uuid4(),
        )
        session.flush()
        assert session.scalar(
            select(AttendanceDayRemark).where(AttendanceDayRemark.id == remark.id)
        )
        remark.remark = "Mutated"
        with pytest.raises(RuntimeError, match="append-only"):
            session.flush()
        session.rollback()
    finally:
        session.close()
