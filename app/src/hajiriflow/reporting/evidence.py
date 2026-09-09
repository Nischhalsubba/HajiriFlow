from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from hajiriflow.db.models.attendance_baseline import ManualAttendanceEvent
from hajiriflow.reporting.service import AttendanceReportingService

MAX_EVENT_OFFSET = 5000


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def merged_attendance_events(
    session: Session,
    *,
    organization_id: UUID,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    employee_id: UUID | None = None,
    device_id: UUID | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, object]]:
    """Return one privacy-safe, bounded timeline across device and manual evidence."""
    if limit < 1 or limit > 1000:
        raise ValueError("event page size must be between 1 and 1000")
    if offset < 0 or offset > MAX_EVENT_OFFSET:
        raise ValueError(f"event offset must be between 0 and {MAX_EVENT_OFFSET}")
    fetch_limit = min(6000, limit + offset)
    service = AttendanceReportingService(session)
    device_rows = service.attendance_events(
        organization_id=organization_id,
        from_at=from_at,
        to_at=to_at,
        employee_id=employee_id,
        device_id=device_id,
        limit=fetch_limit,
        offset=0,
    )
    for row in device_rows:
        row.setdefault("received_at", row["occurred_at"])
        row.setdefault("punch_kind", row["event_type"])

    manual_rows: list[dict[str, object]] = []
    if device_id is None:
        query = select(ManualAttendanceEvent).where(
            ManualAttendanceEvent.organization_id == organization_id
        )
        if employee_id is not None:
            query = query.where(ManualAttendanceEvent.employee_id == employee_id)
        if from_at is not None:
            query = query.where(ManualAttendanceEvent.event_time >= _as_utc(from_at))
        if to_at is not None:
            query = query.where(ManualAttendanceEvent.event_time <= _as_utc(to_at))
        items = session.scalars(
            query.order_by(
                ManualAttendanceEvent.event_time.desc(),
                ManualAttendanceEvent.id.desc(),
            ).limit(fetch_limit)
        ).all()
        manual_rows = [
            {
                "id": item.id,
                "employee_id": item.employee_id,
                "source": "manual",
                "device_id": None,
                "occurred_at": _as_utc(item.event_time),
                "received_at": _as_utc(item.requested_at),
                "event_type": item.event_type,
                "punch_kind": item.event_type,
                "verification_method": None,
                "source_fingerprint": None,
                "manual_status": item.status,
            }
            for item in items
        ]

    merged = [*device_rows, *manual_rows]
    merged.sort(
        key=lambda item: (
            item["occurred_at"],
            str(item["id"]),
        ),
        reverse=True,
    )
    return merged[offset : offset + limit]
