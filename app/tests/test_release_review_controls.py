from decimal import Decimal

import pytest

from hajiriflow.db.session import get_session_factory
from hajiriflow.operations.reconciliation import (
    payroll_line_is_balanced,
    reconcile_release_data,
)

pytestmark = pytest.mark.usefixtures("database")


def test_empty_release_database_reconciles_cleanly() -> None:
    session = get_session_factory()()
    try:
        report = reconcile_release_data(session)
    finally:
        session.close()
    assert report["ok"] is True
    assert report["attendance"]["records_without_v2_detail"] == 0
    assert report["payroll"]["math_mismatches"] == 0
    assert report["payroll"]["snapshot_gaps"] == 0
    assert report["payroll"]["terminal_runs_without_lines"] == 0


def test_payroll_reconciliation_uses_exact_decimal_arithmetic() -> None:
    assert payroll_line_is_balanced(
        gross=Decimal("100000.00"),
        deductions=Decimal("5000.00"),
        tax=Decimal("10000.00"),
        net=Decimal("85000.00"),
    )
    assert not payroll_line_is_balanced(
        gross=Decimal("100000.00"),
        deductions=Decimal("5000.00"),
        tax=Decimal("10000.00"),
        net=Decimal("84999.99"),
    )
