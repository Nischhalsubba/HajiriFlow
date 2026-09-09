import argparse
import json
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hajiriflow.db.models.attendance import AttendanceRecord
from hajiriflow.db.models.attendance_baseline import AttendanceRecordDetail
from hajiriflow.db.models.payroll import PayrollLine, PayrollRun
from hajiriflow.db.session import get_session_factory


def payroll_line_is_balanced(
    *,
    gross: Decimal,
    deductions: Decimal,
    tax: Decimal,
    net: Decimal,
) -> bool:
    return gross - deductions - tax == net


def reconcile_release_data(
    session: Session,
    *,
    organization_id: UUID | None = None,
) -> dict:
    attendance_filter = []
    payroll_filter = []
    run_filter = []
    if organization_id is not None:
        attendance_filter.append(AttendanceRecord.organization_id == organization_id)
        payroll_filter.append(PayrollRun.organization_id == organization_id)
        run_filter.append(PayrollRun.organization_id == organization_id)

    attendance_total = int(
        session.scalar(
            select(func.count(AttendanceRecord.id)).where(*attendance_filter)
        )
        or 0
    )
    attendance_missing_detail = int(
        session.scalar(
            select(func.count(AttendanceRecord.id))
            .outerjoin(
                AttendanceRecordDetail,
                AttendanceRecordDetail.attendance_record_id == AttendanceRecord.id,
            )
            .where(*attendance_filter, AttendanceRecordDetail.attendance_record_id.is_(None))
        )
        or 0
    )

    line_query = select(PayrollLine).join(PayrollRun, PayrollRun.id == PayrollLine.run_id)
    if payroll_filter:
        line_query = line_query.where(*payroll_filter)
    payroll_lines = list(session.scalars(line_query).all())

    payroll_math_mismatches = 0
    payroll_snapshot_gaps = 0
    for line in payroll_lines:
        if not payroll_line_is_balanced(
            gross=line.gross_amount,
            deductions=line.deduction_amount,
            tax=line.tax_amount,
            net=line.net_amount,
        ):
            payroll_math_mismatches += 1
        snapshots = (
            line.employee_snapshot,
            line.attendance_snapshot,
            line.earnings_snapshot,
            line.deductions_snapshot,
            line.explanation,
        )
        if any(not isinstance(item, dict) for item in snapshots):
            payroll_snapshot_gaps += 1

    terminal_runs_query = select(PayrollRun).where(
        PayrollRun.status.in_(("posted", "reversed")),
        *run_filter,
    )
    terminal_runs = list(session.scalars(terminal_runs_query).all())
    terminal_runs_without_lines = 0
    for run in terminal_runs:
        count = int(
            session.scalar(
                select(func.count(PayrollLine.id)).where(PayrollLine.run_id == run.id)
            )
            or 0
        )
        if count == 0:
            terminal_runs_without_lines += 1

    failures = {
        "attendance_records_without_v2_detail": attendance_missing_detail,
        "payroll_math_mismatches": payroll_math_mismatches,
        "payroll_snapshot_gaps": payroll_snapshot_gaps,
        "terminal_payroll_runs_without_lines": terminal_runs_without_lines,
    }
    return {
        "ok": all(value == 0 for value in failures.values()),
        "organization_id": str(organization_id) if organization_id else None,
        "attendance": {
            "records": attendance_total,
            "records_without_v2_detail": attendance_missing_detail,
        },
        "payroll": {
            "lines": len(payroll_lines),
            "terminal_runs": len(terminal_runs),
            "math_mismatches": payroll_math_mismatches,
            "snapshot_gaps": payroll_snapshot_gaps,
            "terminal_runs_without_lines": terminal_runs_without_lines,
        },
        "failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile HajiriFlow attendance and payroll release invariants."
    )
    parser.add_argument(
        "--organization-id",
        help="Optionally scope reconciliation to one organization UUID.",
    )
    args = parser.parse_args(argv)
    organization_id = UUID(args.organization_id) if args.organization_id else None

    session = get_session_factory()()
    try:
        report = reconcile_release_data(session, organization_id=organization_id)
    finally:
        session.close()
    print(json.dumps(report, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
