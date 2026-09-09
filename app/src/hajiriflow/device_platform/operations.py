from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from hajiriflow.db.models.device import Device, DevicePullSession
from hajiriflow.db.models.device_baseline import (
    DeviceOperation,
    DeviceRuntimeConfiguration,
)
from hajiriflow.db.models.identity import AuditEvent
from hajiriflow.device_platform.adapters import DeviceAdapter, PullBatch
from hajiriflow.device_platform.pull import DevicePullCoordinator, device_pull_lock
from hajiriflow.device_platform.service import SENSITIVE_EVIDENCE_TERMS, DevicePlatformService

AdapterResolver = Callable[[Device], DeviceAdapter | None]
MAX_HISTORICAL_DAYS = 366
MAX_HISTORICAL_BATCHES = 100


def utc_now() -> datetime:
    return datetime.now(UTC)


def _safe_metadata(value: dict) -> dict:
    safe: dict = {}
    for key, item in value.items():
        normalized = str(key).casefold().replace("-", "_")
        if any(term in normalized for term in SENSITIVE_EVIDENCE_TERMS):
            continue
        if isinstance(item, (str, int, float, bool, type(None))):
            safe[str(key)] = item
    return safe


class DeviceOperationService:
    def __init__(self, session: Session, *, max_attempts: int = 3) -> None:
        self.session = session
        self.max_attempts = max_attempts
        self.platform = DevicePlatformService(session)
        self.coordinator = DevicePullCoordinator(session, max_attempts=max_attempts)

    def device(self, organization_id: UUID, device_id: UUID) -> Device:
        item = self.session.get(Device, device_id)
        if not item or item.organization_id != organization_id:
            raise LookupError("device not found")
        return item

    def runtime_configuration(
        self,
        *,
        organization_id: UUID,
        device_id: UUID,
    ) -> DeviceRuntimeConfiguration:
        self.device(organization_id, device_id)
        item = self.session.get(DeviceRuntimeConfiguration, device_id)
        if item is None:
            item = DeviceRuntimeConfiguration(
                device_id=device_id,
                organization_id=organization_id,
                protocol_preference="auto",
                timeout_seconds=10,
            )
            self.session.add(item)
            self.session.flush()
        return item

    def update_runtime_configuration(
        self,
        *,
        organization_id: UUID,
        device_id: UUID,
        site: str | None,
        protocol_preference: str,
        timeout_seconds: int,
        actor_user_id: UUID,
    ) -> DeviceRuntimeConfiguration:
        if protocol_preference not in {"auto", "http", "https"}:
            raise ValueError("unsupported protocol preference")
        if timeout_seconds < 1 or timeout_seconds > 120:
            raise ValueError("timeout must be between 1 and 120 seconds")
        item = self.runtime_configuration(
            organization_id=organization_id,
            device_id=device_id,
        )
        before = {
            "site": item.site,
            "protocol_preference": item.protocol_preference,
            "timeout_seconds": item.timeout_seconds,
        }
        item.site = site.strip() if site and site.strip() else None
        item.protocol_preference = protocol_preference
        item.timeout_seconds = timeout_seconds
        item.updated_at = utc_now()
        self.session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action="device.runtime_configuration.update",
                object_type="device",
                object_id=str(device_id),
                before_data=before,
                after_data={
                    "site": item.site,
                    "protocol_preference": item.protocol_preference,
                    "timeout_seconds": item.timeout_seconds,
                },
                context_data={"organization_id": str(organization_id)},
            )
        )
        return item

    def enqueue(
        self,
        *,
        organization_id: UUID,
        device_id: UUID,
        operation_type: str,
        requested_by: UUID,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> DeviceOperation:
        device = self.device(organization_id, device_id)
        if device.status != "active":
            raise ValueError("disabled devices cannot receive operations")
        if operation_type not in {"diagnostics", "immediate_pull", "historical_pull"}:
            raise ValueError("unsupported device operation")
        if operation_type == "historical_pull":
            if window_start is None or window_end is None:
                raise ValueError("historical pulls require start and end timestamps")
            if window_start.tzinfo is None or window_end.tzinfo is None:
                raise ValueError("historical pull timestamps must include a timezone")
            if window_end < window_start:
                raise ValueError("historical pull end cannot be before start")
            if window_end - window_start > timedelta(days=MAX_HISTORICAL_DAYS):
                raise ValueError("historical pull range cannot exceed 366 days")
        elif window_start is not None or window_end is not None:
            raise ValueError("date ranges are supported only for historical pulls")

        operation = DeviceOperation(
            organization_id=organization_id,
            device_id=device_id,
            requested_by=requested_by,
            operation_type=operation_type,
            window_start=window_start,
            window_end=window_end,
            status="pending",
        )
        self.session.add(operation)
        self.session.flush()
        self.session.add(
            AuditEvent(
                actor_user_id=requested_by,
                action=f"device.operation.{operation_type}.requested",
                object_type="device_operation",
                object_id=str(operation.id),
                after_data={
                    "device_id": str(device_id),
                    "operation_type": operation_type,
                    "window_start": window_start.isoformat() if window_start else None,
                    "window_end": window_end.isoformat() if window_end else None,
                },
                context_data={"organization_id": str(organization_id)},
            )
        )
        return operation

    def pending(self, *, limit: int = 25) -> tuple[DeviceOperation, ...]:
        query = (
            select(DeviceOperation)
            .where(DeviceOperation.status == "pending")
            .order_by(DeviceOperation.created_at, DeviceOperation.id)
            .limit(max(1, min(limit, 100)))
        )
        if self.session.get_bind().dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        return tuple(self.session.scalars(query).all())

    @staticmethod
    def _finish_pull_failure(
        pull_session: DevicePullSession,
        *,
        code: str,
        detail: str,
        inserted: int = 0,
        duplicates: int = 0,
    ) -> DevicePullSession:
        pull_session.status = "failed"
        pull_session.error_code = code[:100]
        pull_session.error_detail = detail
        pull_session.ingested_count = inserted
        pull_session.duplicate_count = duplicates
        pull_session.ended_at = utc_now()
        return pull_session

    def _pull_historical(
        self,
        *,
        operation: DeviceOperation,
        device: Device,
        adapter: DeviceAdapter,
    ) -> DevicePullSession:
        capabilities = adapter.capabilities()
        pull_range = getattr(adapter, "pull_punches_range", None)
        if not capabilities.historical_pulls or not callable(pull_range):
            raise ValueError("registered adapter does not support historical pulls")
        if operation.window_start is None or operation.window_end is None:
            raise ValueError("historical operation is missing its range")

        pull_session = DevicePullSession(
            organization_id=device.organization_id,
            device_id=device.id,
            requested_by=operation.requested_by,
            mode="immediate",
            status="running",
            attempt_count=1,
        )
        self.session.add(pull_session)
        self.session.flush()

        with device_pull_lock(self.session, device.id) as acquired:
            if not acquired:
                pull_session.status = "skipped"
                pull_session.error_code = "device_locked"
                pull_session.error_detail = "Another worker is already pulling this device."
                pull_session.ended_at = utc_now()
                return pull_session

            cursor: str | None = None
            seen_cursors: set[str] = set()
            total_inserted = 0
            total_duplicates = 0
            for _batch_number in range(MAX_HISTORICAL_BATCHES):
                batch: PullBatch | None = None
                failure: Exception | None = None
                for attempt in range(1, self.max_attempts + 1):
                    pull_session.attempt_count = max(pull_session.attempt_count, attempt)
                    try:
                        batch = pull_range(
                            start_at=operation.window_start,
                            end_at=operation.window_end,
                            cursor=cursor,
                        )
                        failure = None
                        break
                    except Exception as exc:
                        failure = exc
                if batch is None:
                    error_code = type(failure).__name__ if failure else "pull_failed"
                    return self._finish_pull_failure(
                        pull_session,
                        code=error_code,
                        detail="Historical device pull failed after bounded retries.",
                        inserted=total_inserted,
                        duplicates=total_duplicates,
                    )

                with self.session.begin_nested():
                    inserted, duplicates = self.platform.ingest_punches(
                        device=device,
                        punches=batch.punches,
                        pull_session=pull_session,
                    )
                total_inserted += inserted
                total_duplicates += duplicates
                pull_session.cursor_after = batch.next_cursor
                if not batch.next_cursor:
                    pull_session.ingested_count = total_inserted
                    pull_session.duplicate_count = total_duplicates
                    pull_session.status = "succeeded"
                    pull_session.ended_at = utc_now()
                    device.last_seen_at = pull_session.ended_at
                    return pull_session
                if batch.next_cursor in seen_cursors:
                    return self._finish_pull_failure(
                        pull_session,
                        code="cursor_cycle",
                        detail="Historical adapter repeated a pagination cursor.",
                        inserted=total_inserted,
                        duplicates=total_duplicates,
                    )
                seen_cursors.add(batch.next_cursor)
                cursor = batch.next_cursor

        return self._finish_pull_failure(
            pull_session,
            code="batch_limit",
            detail="Historical pull exceeded the bounded batch limit.",
            inserted=total_inserted,
            duplicates=total_duplicates,
        )

    def process(
        self,
        operation: DeviceOperation,
        *,
        adapter_resolver: AdapterResolver,
    ) -> DeviceOperation:
        if operation.status != "pending":
            return operation
        device = self.device(operation.organization_id, operation.device_id)
        operation.status = "running"
        operation.started_at = utc_now()
        operation.error_code = None
        operation.error_detail = None
        self.session.flush()
        try:
            adapter = adapter_resolver(device)
            if adapter is None:
                operation.status = "skipped"
                operation.error_code = "adapter_unavailable"
                operation.error_detail = "No supported adapter is configured for this device."
                return operation

            runtime = self.runtime_configuration(
                organization_id=device.organization_id,
                device_id=device.id,
            )
            if operation.operation_type == "diagnostics":
                result = adapter.diagnostics()
                operation.result_data = {
                    "reachable": result.reachable,
                    "observed_at": result.observed_at.isoformat(),
                    "firmware_version": result.firmware_version,
                    "device_time": result.device_time.isoformat() if result.device_time else None,
                    "message": result.message,
                    "metadata": _safe_metadata(result.metadata),
                }
                operation.status = "succeeded" if result.reachable else "failed"
                if not result.reachable:
                    operation.error_code = "device_unreachable"
                    operation.error_detail = (
                        "Device diagnostics reported that the device is unreachable."
                    )
                runtime.last_diagnostics_at = result.observed_at
                if result.reachable:
                    device.last_seen_at = result.observed_at
            elif operation.operation_type == "immediate_pull":
                pull = self.coordinator.pull_device(
                    device=device,
                    adapter=adapter,
                    mode="immediate",
                    requested_by=operation.requested_by,
                )
                operation.result_data = {
                    "pull_session_id": str(pull.id),
                    "ingested_count": pull.ingested_count,
                    "duplicate_count": pull.duplicate_count,
                }
                operation.status = pull.status
                operation.error_code = pull.error_code
                operation.error_detail = pull.error_detail
                if pull.status == "succeeded":
                    runtime.last_successful_pull_at = pull.ended_at
            else:
                pull = self._pull_historical(
                    operation=operation,
                    device=device,
                    adapter=adapter,
                )
                if operation.window_start is None or operation.window_end is None:
                    raise ValueError("historical operation is missing its range")
                operation.result_data = {
                    "pull_session_id": str(pull.id),
                    "ingested_count": pull.ingested_count,
                    "duplicate_count": pull.duplicate_count,
                    "window_start": operation.window_start.isoformat(),
                    "window_end": operation.window_end.isoformat(),
                }
                operation.status = pull.status
                operation.error_code = pull.error_code
                operation.error_detail = pull.error_detail
                if pull.status == "succeeded":
                    runtime.last_successful_pull_at = pull.ended_at
        except Exception as exc:
            operation.status = "failed"
            operation.error_code = type(exc).__name__[:100]
            operation.error_detail = (
                "Device operation failed; see sanitized worker diagnostics."
            )
        finally:
            operation.ended_at = utc_now()
            self.session.flush()
        return operation

    def process_pending(
        self,
        *,
        adapter_resolver: AdapterResolver,
        limit: int = 25,
    ) -> tuple[DeviceOperation, ...]:
        results: list[DeviceOperation] = []
        for operation in self.pending(limit=limit):
            results.append(self.process(operation, adapter_resolver=adapter_resolver))
        return tuple(results)
