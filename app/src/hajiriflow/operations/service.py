from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from hajiriflow.db.models.attendance import AttendanceRecord
from hajiriflow.db.models.attendance_baseline import AttendanceRecordDetail
from hajiriflow.db.models.device import Device, DevicePullSession
from hajiriflow.db.models.device_baseline import DeviceOperation, DeviceRuntimeConfiguration
from hajiriflow.db.models.payroll import PayrollRun
from hajiriflow.db.models.workforce import CompanyProfile


def utc_now() -> datetime:
    return datetime.now(UTC)


def _count(session: Session, statement) -> int:
    return int(session.scalar(statement) or 0)


class OperationalDashboardService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def snapshot(
        self,
        *,
        organization_id: UUID,
        work_date: date | None = None,
        stale_after_minutes: int = 30,
        now: datetime | None = None,
    ) -> dict:
        organization = self.session.get(CompanyProfile, organization_id)
        if organization is None:
            raise LookupError("organization not found")
        if stale_after_minutes < 5 or stale_after_minutes > 1440:
            raise ValueError("stale threshold must be between 5 and 1440 minutes")
        observed_at = now or utc_now()
        report_date = work_date or observed_at.date()
        recent_from = observed_at - timedelta(hours=24)
        stale_before = observed_at - timedelta(minutes=stale_after_minutes)

        device_counts = {
            status: count
            for status, count in self.session.execute(
                select(Device.status, func.count(Device.id))
                .where(Device.organization_id == organization_id)
                .group_by(Device.status)
            ).all()
        }
        stale_devices = _count(
            self.session,
            select(func.count(Device.id))
            .outerjoin(
                DeviceRuntimeConfiguration,
                DeviceRuntimeConfiguration.device_id == Device.id,
            )
            .where(
                Device.organization_id == organization_id,
                Device.status == "active",
                or_(
                    func.coalesce(
                        DeviceRuntimeConfiguration.last_successful_pull_at,
                        Device.last_seen_at,
                    ).is_(None),
                    func.coalesce(
                        DeviceRuntimeConfiguration.last_successful_pull_at,
                        Device.last_seen_at,
                    )
                    < stale_before,
                ),
            ),
        )

        pull_counts = {
            status: count
            for status, count in self.session.execute(
                select(DevicePullSession.status, func.count(DevicePullSession.id))
                .where(
                    DevicePullSession.organization_id == organization_id,
                    DevicePullSession.started_at >= recent_from,
                )
                .group_by(DevicePullSession.status)
            ).all()
        }
        recent_pull_failures = [
            {
                "device_id": str(device_id),
                "error_code": error_code,
                "started_at": started_at.isoformat(),
            }
            for device_id, error_code, started_at in self.session.execute(
                select(
                    DevicePullSession.device_id,
                    DevicePullSession.error_code,
                    DevicePullSession.started_at,
                )
                .where(
                    DevicePullSession.organization_id == organization_id,
                    DevicePullSession.status == "failed",
                    DevicePullSession.started_at >= recent_from,
                )
                .order_by(DevicePullSession.started_at.desc())
                .limit(20)
            ).all()
        ]

        operation_counts = {
            status: count
            for status, count in self.session.execute(
                select(DeviceOperation.status, func.count(DeviceOperation.id))
                .where(
                    DeviceOperation.organization_id == organization_id,
                    DeviceOperation.created_at >= recent_from,
                )
                .group_by(DeviceOperation.status)
            ).all()
        }
        oldest_pending = self.session.scalar(
            select(func.min(DeviceOperation.created_at)).where(
                DeviceOperation.organization_id == organization_id,
                DeviceOperation.status == "pending",
            )
        )

        attendance_counts = {
            status: count
            for status, count in self.session.execute(
                select(AttendanceRecordDetail.day_status, func.count(AttendanceRecord.id))
                .join(
                    AttendanceRecordDetail,
                    AttendanceRecordDetail.attendance_record_id == AttendanceRecord.id,
                )
                .where(
                    AttendanceRecord.organization_id == organization_id,
                    AttendanceRecord.work_date == report_date,
                )
                .group_by(AttendanceRecordDetail.day_status)
            ).all()
        }
        attendance_exceptions = sum(
            attendance_counts.get(key, 0) for key in ("absent", "partial")
        )

        payroll_counts = {
            status: count
            for status, count in self.session.execute(
                select(PayrollRun.status, func.count(PayrollRun.id))
                .where(PayrollRun.organization_id == organization_id)
                .group_by(PayrollRun.status)
            ).all()
        }

        alerts: list[dict] = []
        if stale_devices:
            alerts.append(
                {
                    "code": "stale_devices",
                    "severity": "warning",
                    "count": stale_devices,
                }
            )
        failed_pulls = pull_counts.get("failed", 0)
        if failed_pulls:
            alerts.append(
                {
                    "code": "pull_failures_24h",
                    "severity": "warning",
                    "count": failed_pulls,
                }
            )
        failed_jobs = operation_counts.get("failed", 0)
        if failed_jobs:
            alerts.append(
                {
                    "code": "worker_job_failures_24h",
                    "severity": "critical",
                    "count": failed_jobs,
                }
            )
        if attendance_exceptions:
            alerts.append(
                {
                    "code": "attendance_exceptions",
                    "severity": "info",
                    "count": attendance_exceptions,
                }
            )
        pending_payroll = payroll_counts.get("submitted", 0) + payroll_counts.get(
            "reversal_pending", 0
        )
        if pending_payroll:
            alerts.append(
                {
                    "code": "payroll_approval_pending",
                    "severity": "info",
                    "count": pending_payroll,
                }
            )

        return {
            "organization_id": str(organization_id),
            "generated_at": observed_at.isoformat(),
            "work_date": report_date.isoformat(),
            "stale_after_minutes": stale_after_minutes,
            "devices": {
                "total": sum(device_counts.values()),
                "active": device_counts.get("active", 0),
                "disabled": device_counts.get("disabled", 0),
                "error": device_counts.get("error", 0),
                "stale": stale_devices,
            },
            "pulls_24h": {
                "running": pull_counts.get("running", 0),
                "succeeded": pull_counts.get("succeeded", 0),
                "failed": pull_counts.get("failed", 0),
                "skipped": pull_counts.get("skipped", 0),
                "recent_failures": recent_pull_failures,
            },
            "jobs_24h": {
                "pending": operation_counts.get("pending", 0),
                "running": operation_counts.get("running", 0),
                "succeeded": operation_counts.get("succeeded", 0),
                "failed": operation_counts.get("failed", 0),
                "skipped": operation_counts.get("skipped", 0),
                "oldest_pending_at": oldest_pending.isoformat() if oldest_pending else None,
            },
            "attendance": {
                "statuses": attendance_counts,
                "exceptions": attendance_exceptions,
            },
            "payroll": {
                "statuses": payroll_counts,
                "approval_pending": pending_payroll,
            },
            "alerts": alerts,
        }
