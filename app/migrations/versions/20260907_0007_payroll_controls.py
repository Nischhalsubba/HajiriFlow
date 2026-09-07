"""Add auditable payroll periods, runs, lines, and reversals.

Revision ID: 20260907_0007
Revises: 20260907_0006
Create Date: 2026-09-07
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_0007"
down_revision: str | None = "20260907_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payroll_periods",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attendance_calculation_version", sa.String(length=80), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_by", sa.Uuid(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", sa.Uuid(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("ends_on >= starts_on", name="payroll_period_valid_dates"),
        sa.CheckConstraint(
            "status IN ('open', 'locked', 'closed')",
            name="payroll_period_valid_status",
        ),
        sa.CheckConstraint(
            "(status = 'open' AND locked_at IS NULL AND locked_by IS NULL) OR "
            "(status IN ('locked', 'closed') AND locked_at IS NOT NULL AND locked_by IS NOT NULL)",
            name="payroll_period_lock_consistency",
        ),
        sa.CheckConstraint(
            "(status <> 'closed' AND closed_at IS NULL AND closed_by IS NULL) OR "
            "(status = 'closed' AND closed_at IS NOT NULL AND closed_by IS NOT NULL)",
            name="payroll_period_close_consistency",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["locked_by"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["closed_by"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_payroll_period_org_code"),
    )
    op.create_index(
        "ix_payroll_periods_org_dates",
        "payroll_periods",
        ["organization_id", "starts_on", "ends_on"],
        unique=False,
    )
    op.create_index(
        "ix_payroll_periods_org_status",
        "payroll_periods",
        ["organization_id", "status"],
        unique=False,
    )

    op.create_table(
        "payroll_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("period_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("calculation_version", sa.String(length=80), nullable=False),
        sa.Column("policy_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posted_by", sa.Uuid(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversal_requested_by", sa.Uuid(), nullable=True),
        sa.Column("reversal_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_by", sa.Uuid(), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversal_reason", sa.Text(), nullable=True),
        sa.Column("reversal_of_run_id", sa.Uuid(), nullable=True),
        sa.Column("reversal_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'pending_approval', 'approved', 'posted', "
            "'reversal_pending', 'reversed')",
            name="payroll_run_valid_status",
        ),
        sa.CheckConstraint("sequence >= 1", name="payroll_run_positive_sequence"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["period_id"], ["payroll_periods.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["posted_by"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["reversal_requested_by"], ["user_accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["reversed_by"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["reversal_of_run_id"], ["payroll_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reversal_run_id"], ["payroll_runs.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("period_id", "sequence", name="uq_payroll_run_period_sequence"),
    )
    op.create_index(
        "ix_payroll_runs_org_status",
        "payroll_runs",
        ["organization_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_payroll_runs_period_status",
        "payroll_runs",
        ["period_id", "status"],
        unique=False,
    )

    op.create_table(
        "payroll_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("gross_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("deduction_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("net_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("employee_snapshot", sa.JSON(), nullable=False),
        sa.Column("attendance_snapshot", sa.JSON(), nullable=False),
        sa.Column("earnings_snapshot", sa.JSON(), nullable=False),
        sa.Column("deductions_snapshot", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "direction IN ('payroll', 'reversal')",
            name="payroll_line_valid_direction",
        ),
        sa.CheckConstraint("gross_amount >= 0", name="payroll_line_nonnegative_gross"),
        sa.CheckConstraint(
            "deduction_amount >= 0",
            name="payroll_line_nonnegative_deduction",
        ),
        sa.CheckConstraint("tax_amount >= 0", name="payroll_line_nonnegative_tax"),
        sa.CheckConstraint("net_amount >= 0", name="payroll_line_nonnegative_net"),
        sa.ForeignKeyConstraint(["run_id"], ["payroll_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "employee_id", name="uq_payroll_line_run_employee"),
    )
    op.create_index(
        "ix_payroll_lines_employee",
        "payroll_lines",
        ["employee_id"],
        unique=False,
    )

    op.create_table(
        "payroll_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["payroll_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["user_accounts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_payroll_history_run_time",
        "payroll_history",
        ["run_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_payroll_history_org_time",
        "payroll_history",
        ["organization_id", "occurred_at"],
        unique=False,
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION prevent_payroll_history_mutation() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'payroll_history is immutable';
            END;
            $$
            """
        )
        op.execute(
            """
            CREATE TRIGGER payroll_history_immutable
            BEFORE UPDATE OR DELETE ON payroll_history
            FOR EACH ROW EXECUTE FUNCTION prevent_payroll_history_mutation()
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS payroll_history_immutable ON payroll_history")
        op.execute("DROP FUNCTION IF EXISTS prevent_payroll_history_mutation()")

    op.drop_index("ix_payroll_history_org_time", table_name="payroll_history")
    op.drop_index("ix_payroll_history_run_time", table_name="payroll_history")
    op.drop_table("payroll_history")
    op.drop_index("ix_payroll_lines_employee", table_name="payroll_lines")
    op.drop_table("payroll_lines")
    op.drop_index("ix_payroll_runs_period_status", table_name="payroll_runs")
    op.drop_index("ix_payroll_runs_org_status", table_name="payroll_runs")
    op.drop_table("payroll_runs")
    op.drop_index("ix_payroll_periods_org_status", table_name="payroll_periods")
    op.drop_index("ix_payroll_periods_org_dates", table_name="payroll_periods")
    op.drop_table("payroll_periods")
