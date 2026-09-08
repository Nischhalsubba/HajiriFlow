from collections.abc import Mapping
from uuid import uuid4

from sqlalchemy import event
from sqlalchemy.orm import Session

from hajiriflow.core.request_context import current_request_id
from hajiriflow.db.models.identity import AuditEvent
from hajiriflow.identity.audit import redact_audit_payload

BUSINESS_PREFIXES = ("attendance.", "payroll.", "device.", "biometric.")

PREVIOUS_STATUS_BY_ACTION = {
    "payroll.period.locked": "open",
    "payroll.period.closed": "locked",
    "payroll.run.submitted": "draft",
    "payroll.run.approved": "pending_approval",
    "payroll.run.posted": "approved",
    "payroll.reversal.requested": "posted",
    "payroll.reversal.approved": "reversal_pending",
}

APPROVAL_ACTIONS = {
    "attendance.correction_approved",
    "attendance.correction_rejected",
    "payroll.period.locked",
    "payroll.period.closed",
    "payroll.run.approved",
    "payroll.run.posted",
    "payroll.reversal.approved",
    "payroll.reversal.posted",
    "biometric.deletion.complete",
    "biometric.deletion.fail",
}


def _business_source(action: str) -> str | None:
    for prefix in BUSINESS_PREFIXES:
        if action.startswith(prefix):
            return prefix[:-1]
    return None


def _safe_context(value: Mapping[str, object] | None) -> dict[str, object]:
    if value is None:
        return {}
    redacted = redact_audit_payload(dict(value))
    if not isinstance(redacted, dict):
        raise TypeError("audit context must be a mapping")
    return redacted


def _complete_business_event(item: AuditEvent) -> None:
    source = _business_source(item.action)
    if source is None:
        return

    context = _safe_context(item.context_data)
    organization_id = str(context.get("organization_id") or "").strip()
    if not organization_id:
        raise ValueError(
            f"business audit event {item.action!r} requires organization_id context"
        )

    context.setdefault("source", source)
    context.setdefault(
        "actor_reference",
        str(item.actor_user_id) if item.actor_user_id is not None else "system",
    )
    context.setdefault(
        "actor_type",
        "user" if item.actor_user_id is not None else "system",
    )

    if item.action in APPROVAL_ACTIONS:
        if not item.object_id:
            raise ValueError(
                f"approval audit event {item.action!r} requires an object reference"
            )
        context.setdefault("approval_reference", item.object_id)

    previous_status = PREVIOUS_STATUS_BY_ACTION.get(item.action)
    if previous_status and item.before_data is None:
        item.before_data = {"status": previous_status}

    if item.action == "device.credential.rotate" and item.before_data is None:
        after = item.after_data or {}
        version = after.get("credential_version") if isinstance(after, dict) else None
        if isinstance(version, int):
            item.before_data = {
                "credential_version": version - 1 if version > 1 else None
            }

    if item.after_data is None:
        raise ValueError(
            f"business audit event {item.action!r} requires a redacted new-state snapshot"
        )

    if item.request_id is None:
        item.request_id = current_request_id() or f"op-{uuid4()}"

    item.before_data = (
        redact_audit_payload(item.before_data) if item.before_data is not None else None
    )
    item.after_data = redact_audit_payload(item.after_data)
    item.context_data = context


@event.listens_for(Session, "before_flush")
def enforce_business_audit_contract(
    session: Session,
    _flush_context: object,
    _instances: object,
) -> None:
    for item in session.new:
        if isinstance(item, AuditEvent):
            _complete_business_event(item)
