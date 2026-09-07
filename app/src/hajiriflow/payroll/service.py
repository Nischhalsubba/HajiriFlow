from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hajiriflow.db.models.identity import AuditEvent
from hajiriflow.db.models.payroll import (
    PayrollHistory,
    PayrollLine,
    PayrollPeriod,
    PayrollRun,
)
from hajiriflow.db.models.workforce import CompanyProfile, Employee
from hajiriflow.identity.audit import redact_audit_payload
from hajiriflow.identity.permissions import PermissionGrant, has_permission

PAYROLL_READ = "payroll.read"
PAYROLL_MANAGE = "payroll.manage"
PAYROLL_APPROVE = "payroll.approve"
PAYROLL_EXPORT = "payroll.export"
MONEY = Decimal("0.01")


def utc_now() -> datetime:
    return datetime.now(UTC)


def _money(value: Decimal | int | str) -> Decimal:
    amount = Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)
    if amount < 0:
        raise ValueError("payroll amounts cannot be negative")
    return amount


def _run_snapshot(run: PayrollRun) -> dict[str, object]:
    return {
        "period_id": str(run.period_id),
        "sequence": run.sequence,
        "status": run.status,
        "calculation_version": run.calculation_version,
        "reversal_of_run_id": str(run.reversal_of_run_id) if run.reversal_of_run_id else None,
        "reversal_run_id": str(run.reversal_run_id) if run.reversal_run_id else None,
    }


class PayrollService:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _require(
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
        permission: str,
        organization_id: UUID,
    ) -> None:
        if not has_permission(grants, permission, organization_id=organization_id):
            raise PermissionError(f"missing {permission} permission")

    def _organization(self, organization_id: UUID) -> CompanyProfile:
        organization = self.session.get(CompanyProfile, organization_id)
        if not organization:
            raise LookupError("organization not found")
        return organization

    def _period(self, organization_id: UUID, period_id: UUID) -> PayrollPeriod:
        period = self.session.get(PayrollPeriod, period_id)
        if not period or period.organization_id != organization_id:
            raise LookupError("payroll period not found")
        return period

    def _run(self, organization_id: UUID, run_id: UUID) -> PayrollRun:
        run = self.session.get(PayrollRun, run_id)
        if not run or run.organization_id != organization_id:
            raise LookupError("payroll run not found")
        return run

    def _history(
        self,
        *,
        run: PayrollRun,
        actor_user_id: UUID,
        action: str,
        reason: str | None = None,
        snapshot: dict | None = None,
    ) -> None:
        self.session.add(
            PayrollHistory(
                organization_id=run.organization_id,
                run_id=run.id,
                actor_user_id=actor_user_id,
                action=action,
                reason=reason,
                snapshot=redact_audit_payload(snapshot or _run_snapshot(run)),
            )
        )
        self.session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action=f"payroll.{action}",
                object_type="payroll_run",
                object_id=str(run.id),
                reason=reason,
                after_data=redact_audit_payload(snapshot or _run_snapshot(run)),
                context_data={"organization_id": str(run.organization_id)},
            )
        )
        self.session.flush()

    def create_period(
        self,
        *,
        organization_id: UUID,
        code: str,
        label: str,
        starts_on: date,
        ends_on: date,
        attendance_calculation_version: str,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> PayrollPeriod:
        self._require(grants, PAYROLL_MANAGE, organization_id)
        self._organization(organization_id)
        if ends_on < starts_on:
            raise ValueError("payroll period end must be on or after its start")
        if not attendance_calculation_version.strip():
            raise ValueError("attendance calculation version is required")
        overlap = self.session.scalar(
            select(PayrollPeriod.id).where(
                PayrollPeriod.organization_id == organization_id,
                PayrollPeriod.starts_on <= ends_on,
                PayrollPeriod.ends_on >= starts_on,
            )
        )
        if overlap:
            raise ValueError("payroll periods cannot overlap")
        period = PayrollPeriod(
            organization_id=organization_id,
            code=code.strip(),
            label=label.strip(),
            starts_on=starts_on,
            ends_on=ends_on,
            attendance_calculation_version=attendance_calculation_version.strip(),
            created_by=actor_user_id,
        )
        self.session.add(period)
        self.session.flush()
        self.session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action="payroll.period.created",
                object_type="payroll_period",
                object_id=str(period.id),
                after_data={
                    "code": period.code,
                    "starts_on": period.starts_on.isoformat(),
                    "ends_on": period.ends_on.isoformat(),
                    "attendance_calculation_version": period.attendance_calculation_version,
                },
                context_data={"organization_id": str(organization_id)},
            )
        )
        return period

    def lock_period(
        self,
        *,
        organization_id: UUID,
        period_id: UUID,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> PayrollPeriod:
        self._require(grants, PAYROLL_APPROVE, organization_id)
        period = self._period(organization_id, period_id)
        if period.status != "open":
            raise ValueError("only open payroll periods can be locked")
        if period.created_by == actor_user_id:
            raise ValueError("payroll period locking requires independent approval")
        period.status = "locked"
        period.locked_by = actor_user_id
        period.locked_at = utc_now()
        self.session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action="payroll.period.locked",
                object_type="payroll_period",
                object_id=str(period.id),
                after_data={"status": period.status},
                context_data={"organization_id": str(organization_id)},
            )
        )
        return period

    def create_run(
        self,
        *,
        organization_id: UUID,
        period_id: UUID,
        calculation_version: str,
        policy_snapshot: dict,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> PayrollRun:
        self._require(grants, PAYROLL_MANAGE, organization_id)
        period = self._period(organization_id, period_id)
        if period.status != "locked":
            raise ValueError("payroll generation requires a locked period")
        if not calculation_version.strip():
            raise ValueError("payroll calculation version is required")
        if not policy_snapshot:
            raise ValueError("payroll policy snapshot is required")
        sequence = int(
            self.session.scalar(
                select(func.max(PayrollRun.sequence)).where(PayrollRun.period_id == period.id)
            )
            or 0
        ) + 1
        run = PayrollRun(
            organization_id=organization_id,
            period_id=period.id,
            sequence=sequence,
            calculation_version=calculation_version.strip(),
            policy_snapshot=redact_audit_payload(policy_snapshot),
            created_by=actor_user_id,
        )
        self.session.add(run)
        self.session.flush()
        self._history(run=run, actor_user_id=actor_user_id, action="run.created")
        return run

    def add_line(
        self,
        *,
        organization_id: UUID,
        run_id: UUID,
        employee_id: UUID,
        gross_amount: Decimal | int | str,
        deduction_amount: Decimal | int | str,
        tax_amount: Decimal | int | str,
        employee_snapshot: dict,
        attendance_snapshot: dict,
        earnings_snapshot: dict,
        deductions_snapshot: dict,
        explanation: dict,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> PayrollLine:
        self._require(grants, PAYROLL_MANAGE, organization_id)
        run = self._run(organization_id, run_id)
        if run.status != "draft":
            raise ValueError("payroll lines can only change while a run is draft")
        employee = self.session.get(Employee, employee_id)
        if not employee or employee.organization_id != organization_id:
            raise LookupError("employee not found")
        if self.session.scalar(
            select(PayrollLine.id).where(
                PayrollLine.run_id == run.id,
                PayrollLine.employee_id == employee_id,
            )
        ):
            raise ValueError("employee already has a payroll line in this run")
        gross = _money(gross_amount)
        deductions = _money(deduction_amount)
        tax = _money(tax_amount)
        if deductions + tax > gross:
            raise ValueError("deductions and tax cannot exceed gross pay")
        line = PayrollLine(
            run_id=run.id,
            employee_id=employee_id,
            direction="payroll",
            currency="NPR",
            gross_amount=gross,
            deduction_amount=deductions,
            tax_amount=tax,
            net_amount=(gross - deductions - tax).quantize(MONEY),
            employee_snapshot=redact_audit_payload(employee_snapshot),
            attendance_snapshot=redact_audit_payload(attendance_snapshot),
            earnings_snapshot=redact_audit_payload(earnings_snapshot),
            deductions_snapshot=redact_audit_payload(deductions_snapshot),
            explanation=redact_audit_payload(explanation),
        )
        self.session.add(line)
        self.session.flush()
        self._history(
            run=run,
            actor_user_id=actor_user_id,
            action="line.added",
            snapshot={"employee_id": str(employee_id), "net_amount": str(line.net_amount)},
        )
        return line

    def submit_run(
        self,
        *,
        organization_id: UUID,
        run_id: UUID,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> PayrollRun:
        self._require(grants, PAYROLL_MANAGE, organization_id)
        run = self._run(organization_id, run_id)
        if run.status != "draft":
            raise ValueError("only draft payroll runs can be submitted")
        line_count = int(
            self.session.scalar(
                select(func.count(PayrollLine.id)).where(PayrollLine.run_id == run.id)
            )
            or 0
        )
        if line_count == 0:
            raise ValueError("payroll run must contain at least one employee")
        run.status = "pending_approval"
        run.submitted_at = utc_now()
        self._history(run=run, actor_user_id=actor_user_id, action="run.submitted")
        return run

    def approve_run(
        self,
        *,
        organization_id: UUID,
        run_id: UUID,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> PayrollRun:
        self._require(grants, PAYROLL_APPROVE, organization_id)
        run = self._run(organization_id, run_id)
        if run.status != "pending_approval":
            raise ValueError("only submitted payroll runs can be approved")
        if run.created_by == actor_user_id:
            raise ValueError("payroll maker cannot approve their own run")
        run.status = "approved"
        run.approved_by = actor_user_id
        run.approved_at = utc_now()
        self._history(run=run, actor_user_id=actor_user_id, action="run.approved")
        return run

    def post_run(
        self,
        *,
        organization_id: UUID,
        run_id: UUID,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> PayrollRun:
        self._require(grants, PAYROLL_APPROVE, organization_id)
        run = self._run(organization_id, run_id)
        if run.status != "approved":
            raise ValueError("only approved payroll runs can be posted")
        run.status = "posted"
        run.posted_by = actor_user_id
        run.posted_at = utc_now()
        self._history(run=run, actor_user_id=actor_user_id, action="run.posted")
        return run

    def request_reversal(
        self,
        *,
        organization_id: UUID,
        run_id: UUID,
        actor_user_id: UUID,
        reason: str,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> PayrollRun:
        self._require(grants, PAYROLL_MANAGE, organization_id)
        run = self._run(organization_id, run_id)
        if run.status != "posted":
            raise ValueError("only posted payroll runs can be reversed")
        normalized_reason = reason.strip()
        if len(normalized_reason) < 10:
            raise ValueError("reversal reason must be at least 10 characters")
        run.status = "reversal_pending"
        run.reversal_requested_by = actor_user_id
        run.reversal_requested_at = utc_now()
        run.reversal_reason = normalized_reason
        self._history(
            run=run,
            actor_user_id=actor_user_id,
            action="reversal.requested",
            reason=normalized_reason,
        )
        return run

    def approve_reversal(
        self,
        *,
        organization_id: UUID,
        run_id: UUID,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> PayrollRun:
        self._require(grants, PAYROLL_APPROVE, organization_id)
        original = self._run(organization_id, run_id)
        if original.status != "reversal_pending":
            raise ValueError("payroll run has no pending reversal")
        if original.reversal_requested_by == actor_user_id:
            raise ValueError("payroll reversal requires independent approval")
        sequence = int(
            self.session.scalar(
                select(func.max(PayrollRun.sequence)).where(
                    PayrollRun.period_id == original.period_id
                )
            )
            or 0
        ) + 1
        reversal = PayrollRun(
            organization_id=organization_id,
            period_id=original.period_id,
            sequence=sequence,
            status="posted",
            calculation_version=original.calculation_version,
            policy_snapshot=original.policy_snapshot,
            created_by=original.reversal_requested_by,
            submitted_at=utc_now(),
            approved_by=actor_user_id,
            approved_at=utc_now(),
            posted_by=actor_user_id,
            posted_at=utc_now(),
            reversal_of_run_id=original.id,
        )
        self.session.add(reversal)
        self.session.flush()
        lines = list(
            self.session.scalars(
                select(PayrollLine).where(PayrollLine.run_id == original.id)
            )
        )
        for line in lines:
            self.session.add(
                PayrollLine(
                    run_id=reversal.id,
                    employee_id=line.employee_id,
                    direction="reversal",
                    currency=line.currency,
                    gross_amount=line.gross_amount,
                    deduction_amount=line.deduction_amount,
                    tax_amount=line.tax_amount,
                    net_amount=line.net_amount,
                    employee_snapshot=line.employee_snapshot,
                    attendance_snapshot=line.attendance_snapshot,
                    earnings_snapshot=line.earnings_snapshot,
                    deductions_snapshot=line.deductions_snapshot,
                    explanation={
                        **line.explanation,
                        "reverses_payroll_line_id": str(line.id),
                    },
                )
            )
        original.status = "reversed"
        original.reversed_by = actor_user_id
        original.reversed_at = utc_now()
        original.reversal_run_id = reversal.id
        self.session.flush()
        self._history(
            run=original,
            actor_user_id=actor_user_id,
            action="reversal.approved",
            reason=original.reversal_reason,
        )
        self._history(
            run=reversal,
            actor_user_id=actor_user_id,
            action="reversal.posted",
            reason=original.reversal_reason,
        )
        return reversal

    def close_period(
        self,
        *,
        organization_id: UUID,
        period_id: UUID,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> PayrollPeriod:
        self._require(grants, PAYROLL_APPROVE, organization_id)
        period = self._period(organization_id, period_id)
        if period.status != "locked":
            raise ValueError("only locked payroll periods can be closed")
        unresolved = int(
            self.session.scalar(
                select(func.count(PayrollRun.id)).where(
                    PayrollRun.period_id == period.id,
                    PayrollRun.status.in_(
                        {"draft", "pending_approval", "approved", "reversal_pending"}
                    ),
                )
            )
            or 0
        )
        if unresolved:
            raise ValueError("payroll period has unresolved runs")
        period.status = "closed"
        period.closed_by = actor_user_id
        period.closed_at = utc_now()
        self.session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action="payroll.period.closed",
                object_type="payroll_period",
                object_id=str(period.id),
                after_data={"status": "closed"},
                context_data={"organization_id": str(organization_id)},
            )
        )
        return period

    def read_line(
        self,
        *,
        organization_id: UUID,
        line_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> PayrollLine:
        self._require(grants, PAYROLL_READ, organization_id)
        line = self.session.get(PayrollLine, line_id)
        if not line:
            raise LookupError("payroll line not found")
        run = self._run(organization_id, line.run_id)
        if run.organization_id != organization_id:
            raise LookupError("payroll line not found")
        return line

    def export_rows(
        self,
        *,
        organization_id: UUID,
        run_id: UUID,
        actor_user_id: UUID,
        grants: set[PermissionGrant] | frozenset[PermissionGrant],
    ) -> list[dict[str, str]]:
        self._require(grants, PAYROLL_EXPORT, organization_id)
        run = self._run(organization_id, run_id)
        if run.status not in {"posted", "reversed"}:
            raise ValueError("only posted payroll can be exported")
        rows = list(
            self.session.scalars(
                select(PayrollLine)
                .where(PayrollLine.run_id == run.id)
                .order_by(PayrollLine.employee_id)
            )
        )
        self._history(run=run, actor_user_id=actor_user_id, action="run.exported")
        return [
            {
                "employee_id": str(line.employee_id),
                "direction": line.direction,
                "currency": line.currency,
                "gross": str(line.gross_amount),
                "deductions": str(line.deduction_amount),
                "tax": str(line.tax_amount),
                "net": str(line.net_amount),
            }
            for line in rows
        ]
