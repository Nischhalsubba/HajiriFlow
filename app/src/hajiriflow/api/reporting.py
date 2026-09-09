from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from hajiriflow.api.dependencies import (
    RequestIdentity,
    get_db,
    require_organization_permission,
)
from hajiriflow.api.reporting_v2 import router
from hajiriflow.db.models.payroll import PayrollLine, PayrollPeriod, PayrollRun


class PayrollWorksheetRow(BaseModel):
    employee_id: UUID
    employee_snapshot: dict
    attendance_snapshot: dict
    earnings_snapshot: dict
    deductions_snapshot: dict
    gross_amount: Decimal
    deduction_amount: Decimal
    tax_amount: Decimal
    net_amount: Decimal
    direction: str
    currency: str


class PayrollWorksheet(BaseModel):
    run_id: UUID
    period_id: UUID
    period_code: str
    period_label: str
    run_status: str
    calculation_version: str
    attendance_calculation_version: str
    rows: list[PayrollWorksheetRow]


@router.get("/payroll/{run_id}/worksheet", response_model=PayrollWorksheet)
def attendance_to_salary_worksheet(
    organization_id: UUID,
    run_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("payroll.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> PayrollWorksheet:
    run = session.get(PayrollRun, run_id)
    if not run or run.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="payroll run not found",
        )
    period = session.get(PayrollPeriod, run.period_id)
    if period is None or period.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="payroll period not found",
        )
    lines = session.scalars(
        select(PayrollLine)
        .where(PayrollLine.run_id == run_id)
        .order_by(PayrollLine.employee_id)
    ).all()
    return PayrollWorksheet(
        run_id=run.id,
        period_id=period.id,
        period_code=period.code,
        period_label=period.label,
        run_status=run.status,
        calculation_version=run.calculation_version,
        attendance_calculation_version=period.attendance_calculation_version,
        rows=[
            PayrollWorksheetRow(
                employee_id=line.employee_id,
                employee_snapshot=line.employee_snapshot,
                attendance_snapshot=line.attendance_snapshot,
                earnings_snapshot=line.earnings_snapshot,
                deductions_snapshot=line.deductions_snapshot,
                gross_amount=line.gross_amount,
                deduction_amount=line.deduction_amount,
                tax_amount=line.tax_amount,
                net_amount=line.net_amount,
                direction=line.direction,
                currency=line.currency,
            )
            for line in lines
        ],
    )
