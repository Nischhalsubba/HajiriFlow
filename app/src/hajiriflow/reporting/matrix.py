from collections import defaultdict
from datetime import date, timedelta
from uuid import UUID

from hajiriflow.reporting.service import AttendanceReportingService, STATUS_CODES


def range_register(
    service: AttendanceReportingService,
    *,
    organization_id: UUID,
    from_date: date,
    to_date: date,
    limit: int = 500,
    offset: int = 0,
) -> list[dict[str, object]]:
    """Build the legacy AD-range register while using attendance-v2 day statuses."""
    service.validate_range(from_date, to_date, max_days=62)
    employees = service.employees(
        organization_id=organization_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )
    employee_ids = [item.id for item in employees]
    records = service._records(  # noqa: SLF001 - package-internal bulk primitive
        organization_id=organization_id,
        employee_ids=employee_ids,
        from_date=from_date,
        to_date=to_date,
    )
    context = service._range_context(  # noqa: SLF001 - package-internal bulk primitive
        organization_id=organization_id,
        employee_ids=employee_ids,
        from_date=from_date,
        to_date=to_date,
    )
    rows: list[dict[str, object]] = []
    for employee in employees:
        days: dict[str, str] = {}
        codes: dict[str, str] = {}
        counts: dict[str, int] = defaultdict(int)
        cursor = from_date
        while cursor <= to_date:
            record, detail = records.get((employee.id, cursor), (None, None))
            status = (
                detail.day_status
                if detail
                else record.status
                if record
                else service._fallback_status(  # noqa: SLF001
                    employee_id=employee.id,
                    work_date=cursor,
                    context=context,
                )
            )
            days[cursor.isoformat()] = status
            codes[cursor.isoformat()] = STATUS_CODES[status]
            counts[status] += 1
            cursor += timedelta(days=1)
        rows.append(
            {
                "employee_id": employee.id,
                "employee_code": employee.employee_code,
                "employee_name": employee.display_name,
                "days": days,
                "codes": codes,
                "status_counts": dict(counts),
            }
        )
    return rows
