from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy import func, select

from hajiriflow.attendance.service import AttendanceService
from hajiriflow.db.models.attendance import (
    AttendanceCorrection,
    AttendanceHistory,
    AttendanceRecord,
)
from hajiriflow.db.models.device import (
    Device,
    DeviceEmployeeMapping,
    DeviceUser,
    RawPunch,
)
from hajiriflow.db.models.identity import UserAccount
from hajiriflow.db.models.workforce import (
    CompanyProfile,
    Employee,
    Shift,
    ShiftAssignment,
)
from hajiriflow.db.session import get_session_factory


def _seed_attendance_day(session):
    organization = CompanyProfile(
        legal_name="Acme Pvt Ltd",
        display_name="Acme",
        timezone="Asia/Kathmandu",
    )
    session.add(organization)
    session.flush()

    employee = Employee(
        organization_id=organization.id,
        employee_code="E-001",
        display_name="Employee One",
        joined_on=date(2026, 9, 1),
    )
    requester = UserAccount(
        username="employee.one",
        password_hash="test-hash",
        display_name="Employee One",
    )
    approver = UserAccount(
        username="manager.one",
        password_hash="test-hash",
        display_name="Manager One",
    )
    shift = Shift(
        organization_id=organization.id,
        code="DAY",
        name="Day Shift",
        starts_at=time(9, 0),
        ends_at=time(17, 0),
        break_minutes=60,
        grace_minutes=15,
    )
    session.add_all([employee, requester, approver, shift])
    session.flush()

    assignment = ShiftAssignment(
        organization_id=organization.id,
        shift_id=shift.id,
        employee_id=employee.id,
        organization_node_id=None,
        starts_on=date(2026, 9, 1),
        ends_on=None,
    )
    device = Device(
        organization_id=organization.id,
        code="gate-a",
        name="Front Gate",
        vendor="test-vendor",
        model="virtual",
        serial_number="serial-gate-a",
        adapter_key="test",
        endpoint_uri="test://gate-a",
        capabilities={"pull_punches": True},
    )
    session.add_all([assignment, device])
    session.flush()

    device_user = DeviceUser(
        organization_id=organization.id,
        device_id=device.id,
        external_user_id="42",
        display_name="Employee One",
        privilege="user",
        active=True,
        template_count=1,
        source_hash="a" * 64,
    )
    session.add(device_user)
    session.flush()
    session.add(
        DeviceEmployeeMapping(
            organization_id=organization.id,
            device_user_id=device_user.id,
            employee_id=employee.id,
            status="active",
        )
    )
    session.add_all(
        [
            RawPunch(
                organization_id=organization.id,
                device_id=device.id,
                device_user_identifier="42",
                occurred_at=datetime(2026, 9, 7, 3, 40, tzinfo=UTC),
                punch_kind="in",
                source_fingerprint="1" * 64,
                evidence={"sequence": 1},
            ),
            RawPunch(
                organization_id=organization.id,
                device_id=device.id,
                device_user_identifier="42",
                occurred_at=datetime(2026, 9, 7, 11, 15, tzinfo=UTC),
                punch_kind="out",
                source_fingerprint="2" * 64,
                evidence={"sequence": 2},
            ),
        ]
    )
    session.flush()
    return organization, employee, requester, approver


def test_attendance_is_deterministic_and_versioned(database) -> None:
    del database
    session = get_session_factory()()
    try:
        organization, employee, _requester, _approver = _seed_attendance_day(session)
        service = AttendanceService(session)

        first = service.calculate_day(
            organization_id=organization.id,
            employee_id=employee.id,
            work_date=date(2026, 9, 7),
        )
        assert first.status == "present"
        assert first.source_punch_count == 2
        assert first.worked_minutes == 395
        assert first.late_minutes == 10
        assert first.source_revision == 1

        second = service.calculate_day(
            organization_id=organization.id,
            employee_id=employee.id,
            work_date=date(2026, 9, 7),
        )
        assert second.id == first.id
        assert second.source_revision == 2
        assert session.scalar(select(func.count(AttendanceRecord.id))) == 1
        assert session.scalar(select(func.count(AttendanceHistory.id))) == 2
    finally:
        session.close()


def test_corrections_require_independent_approval(database) -> None:
    del database
    session = get_session_factory()()
    try:
        organization, employee, requester, approver = _seed_attendance_day(session)
        service = AttendanceService(session)
        record = service.calculate_day(
            organization_id=organization.id,
            employee_id=employee.id,
            work_date=date(2026, 9, 7),
        )
        correction = service.request_correction(
            organization_id=organization.id,
            attendance_record_id=record.id,
            requested_by=requester.id,
            reason="Device clock was ten minutes ahead.",
            proposed_check_in_at=datetime(2026, 9, 7, 3, 30, tzinfo=UTC),
        )

        with pytest.raises(ValueError, match="independent approval"):
            service.decide_correction(
                organization_id=organization.id,
                correction_id=correction.id,
                decided_by=requester.id,
                approve=True,
                decision_reason="Verified against the gate log.",
            )

        decided = service.decide_correction(
            organization_id=organization.id,
            correction_id=correction.id,
            decided_by=approver.id,
            approve=True,
            decision_reason="Verified against the gate log.",
        )
        assert decided.status == "approved"
        assert record.source_revision == 2
        assert record.late_minutes == 0
        assert record.worked_minutes == 405
        assert session.scalar(select(func.count(AttendanceCorrection.id))) == 1
        assert session.scalar(select(func.count(AttendanceHistory.id))) == 3
    finally:
        session.close()


def test_only_one_pending_correction_is_allowed(database) -> None:
    del database
    session = get_session_factory()()
    try:
        organization, employee, requester, _approver = _seed_attendance_day(session)
        service = AttendanceService(session)
        record = service.calculate_day(
            organization_id=organization.id,
            employee_id=employee.id,
            work_date=date(2026, 9, 7),
        )
        service.request_correction(
            organization_id=organization.id,
            attendance_record_id=record.id,
            requested_by=requester.id,
            reason="The first punch was recorded late.",
            proposed_check_in_at=datetime(2026, 9, 7, 3, 30, tzinfo=UTC),
        )
        with pytest.raises(ValueError, match="pending correction"):
            service.request_correction(
                organization_id=organization.id,
                attendance_record_id=record.id,
                requested_by=requester.id,
                reason="A second competing correction must be rejected.",
                proposed_check_in_at=datetime(2026, 9, 7, 3, 25, tzinfo=UTC),
            )
    finally:
        session.close()


def test_attendance_history_is_immutable(database) -> None:
    del database
    session = get_session_factory()()
    try:
        organization, employee, _requester, _approver = _seed_attendance_day(session)
        service = AttendanceService(session)
        service.calculate_day(
            organization_id=organization.id,
            employee_id=employee.id,
            work_date=date(2026, 9, 7),
        )
        history = session.scalar(select(AttendanceHistory))
        assert history is not None
        history.reason = "tampered"
        with pytest.raises(RuntimeError, match="immutable"):
            session.flush()
        session.rollback()
    finally:
        session.close()
