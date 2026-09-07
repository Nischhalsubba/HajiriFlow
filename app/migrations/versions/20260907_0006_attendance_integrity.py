"""Add normalized attendance records and correction history.

Revision ID: 20260907_0006
Revises: 20260907_0005
Create Date: 2026-09-07
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_0006"
down_revision: str | None = "20260907_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attendance_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("shift_id", sa.Uuid(), nullable=True),
        sa.Column("check_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worked_minutes", sa.Integer(), nullable=False),
        sa.Column("late_minutes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("calculation_version", sa.String(length=80), nullable=False),
        sa.Column("source_punch_count", sa.Integer(), nullable=False),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('present', 'absent', 'partial')",
            name="attendance_record_valid_status",
        ),
        sa.CheckConstraint(
            "worked_minutes >= 0 AND late_minutes >= 0 AND source_punch_count >= 0",
            name="attendance_record_nonnegative_metrics",
        ),
        sa.CheckConstraint(
            "check_out_at IS NULL OR check_in_at IS NULL OR check_out_at >= check_in_at",
            name="attendance_record_valid_times",
        ),
        sa.CheckConstraint(
            "source_revision >= 1",
            name="attendance_record_positive_revision",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["company_profiles.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["shift_id"],
            ["shifts.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "employee_id",
            "work_date",
            name="uq_attendance_record_employee_day",
        ),
    )
    op.create_index(
        "ix_attendance_records_org_date",
        "attendance_records",
        ["organization_id", "work_date"],
        unique=False,
    )
    op.create_index(
        "ix_attendance_records_employee_date",
        "attendance_records",
        ["employee_id", "work_date"],
        unique=False,
    )

    op.create_table(
        "attendance_corrections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("attendance_record_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("proposed_check_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("proposed_check_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("proposed_status", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="attendance_correction_valid_status",
        ),
        sa.CheckConstraint(
            "proposed_status IS NULL OR proposed_status IN ('present', 'absent', 'partial')",
            name="attendance_correction_valid_proposed_status",
        ),
        sa.CheckConstraint(
            "proposed_check_out_at IS NULL OR proposed_check_in_at IS NULL OR "
            "proposed_check_out_at >= proposed_check_in_at",
            name="attendance_correction_valid_times",
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND decided_at IS NULL AND decided_by IS NULL) OR "
            "(status IN ('approved', 'rejected') AND decided_at IS NOT NULL "
            "AND decided_by IS NOT NULL)",
            name="attendance_correction_decision_consistency",
        ),
        sa.ForeignKeyConstraint(
            ["attendance_record_id"],
            ["attendance_records.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"],
            ["user_accounts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["company_profiles.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["user_accounts.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_attendance_corrections_record_status",
        "attendance_corrections",
        ["attendance_record_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_attendance_corrections_org_requested",
        "attendance_corrections",
        ["organization_id", "requested_at"],
        unique=False,
    )

    op.create_table(
        "attendance_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("attendance_record_id", sa.Uuid(), nullable=False),
        sa.Column("correction_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('calculated', 'recalculated', 'correction_requested', "
            "'correction_approved', 'correction_rejected')",
            name="attendance_history_valid_event_type",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["user_accounts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["attendance_record_id"],
            ["attendance_records.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["correction_id"],
            ["attendance_corrections.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["company_profiles.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_attendance_history_record_time",
        "attendance_history",
        ["attendance_record_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_attendance_history_org_time",
        "attendance_history",
        ["organization_id", "occurred_at"],
        unique=False,
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION prevent_attendance_history_mutation() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'attendance_history is immutable';
            END;
            $$
            """
        )
        op.execute(
            """
            CREATE TRIGGER attendance_history_immutable
            BEFORE UPDATE OR DELETE ON attendance_history
            FOR EACH ROW EXECUTE FUNCTION prevent_attendance_history_mutation()
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS attendance_history_immutable ON attendance_history"
        )
        op.execute("DROP FUNCTION IF EXISTS prevent_attendance_history_mutation()")

    op.drop_index("ix_attendance_history_org_time", table_name="attendance_history")
    op.drop_index("ix_attendance_history_record_time", table_name="attendance_history")
    op.drop_table("attendance_history")
    op.drop_index(
        "ix_attendance_corrections_org_requested",
        table_name="attendance_corrections",
    )
    op.drop_index(
        "ix_attendance_corrections_record_status",
        table_name="attendance_corrections",
    )
    op.drop_table("attendance_corrections")
    op.drop_index(
        "ix_attendance_records_employee_date",
        table_name="attendance_records",
    )
    op.drop_index("ix_attendance_records_org_date", table_name="attendance_records")
    op.drop_table("attendance_records")
