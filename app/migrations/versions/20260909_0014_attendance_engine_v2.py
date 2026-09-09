"""Add manual attendance evidence and deterministic engine details.

Revision ID: 20260909_0014
Revises: 20260909_0013
Create Date: 2026-09-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0014"
down_revision: str | None = "20260909_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attendance_policies",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("duplicate_window_seconds", sa.Integer(), nullable=False),
        sa.Column("pre_shift_window_minutes", sa.Integer(), nullable=False),
        sa.Column("post_shift_window_minutes", sa.Integer(), nullable=False),
        sa.Column("manual_approval_required", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "duplicate_window_seconds >= 0 AND duplicate_window_seconds <= 3600",
            name="attendance_policy_duplicate_window_bounds",
        ),
        sa.CheckConstraint(
            "pre_shift_window_minutes >= 0 AND pre_shift_window_minutes <= 1440",
            name="attendance_policy_pre_shift_bounds",
        ),
        sa.CheckConstraint(
            "post_shift_window_minutes >= 0 AND post_shift_window_minutes <= 1440",
            name="attendance_policy_post_shift_bounds",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["company_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("organization_id"),
    )

    op.create_table(
        "attendance_import_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=240), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("strict_mode", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("valid_rows", sa.Integer(), nullable=False),
        sa.Column("invalid_rows", sa.Integer(), nullable=False),
        sa.Column("applied_rows", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('preview', 'applied', 'rejected')",
            name="attendance_import_session_valid_status",
        ),
        sa.CheckConstraint(
            "total_rows >= 0 AND valid_rows >= 0 AND invalid_rows >= 0 "
            "AND applied_rows >= 0",
            name="attendance_import_session_nonnegative_counts",
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
        sa.ForeignKeyConstraint(
            ["approved_by"],
            ["user_accounts.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "content_sha256",
            name="uq_attendance_import_org_content",
        ),
    )
    op.create_index(
        "ix_attendance_import_sessions_org_created",
        "attendance_import_sessions",
        ["organization_id", "created_at"],
    )

    op.create_table(
        "manual_attendance_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=12), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence_note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("import_session_id", sa.Uuid(), nullable=True),
        sa.Column("import_row_number", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "event_type IN ('in', 'out')",
            name="manual_attendance_event_valid_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'revoked')",
            name="manual_attendance_event_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["company_profiles.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["user_accounts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"],
            ["user_accounts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["import_session_id"],
            ["attendance_import_sessions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "import_session_id",
            "import_row_number",
            name="uq_manual_event_import_row",
        ),
    )
    op.create_index(
        "ix_manual_attendance_events_employee_time",
        "manual_attendance_events",
        ["employee_id", "event_time"],
    )
    op.create_index(
        "ix_manual_attendance_events_org_status",
        "manual_attendance_events",
        ["organization_id", "status"],
    )

    op.create_table(
        "attendance_import_rows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=False),
        sa.Column("normalized_data", sa.JSON(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column("applied_event_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["attendance_import_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["applied_event_id"],
            ["manual_attendance_events.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "row_number", name="uq_attendance_import_row"),
    )
    op.create_index(
        "ix_attendance_import_rows_session_valid",
        "attendance_import_rows",
        ["session_id", "is_valid"],
    )

    op.create_table(
        "attendance_day_remarks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("remark", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["company_profiles.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["user_accounts.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_attendance_day_remarks_employee_date",
        "attendance_day_remarks",
        ["employee_id", "work_date", "created_at"],
    )

    op.create_table(
        "attendance_record_details",
        sa.Column("attendance_record_id", sa.Uuid(), nullable=False),
        sa.Column("day_status", sa.String(length=24), nullable=False),
        sa.Column("planned_minutes", sa.Integer(), nullable=False),
        sa.Column("break_minutes", sa.Integer(), nullable=False),
        sa.Column("early_arrival_minutes", sa.Integer(), nullable=False),
        sa.Column("early_departure_minutes", sa.Integer(), nullable=False),
        sa.Column("late_departure_minutes", sa.Integer(), nullable=False),
        sa.Column("regular_overtime_minutes", sa.Integer(), nullable=False),
        sa.Column("holiday_overtime_minutes", sa.Integer(), nullable=False),
        sa.Column("duplicate_event_count", sa.Integer(), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("engine_version", sa.String(length=80), nullable=False),
        sa.Column("explanation_trace", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "day_status IN ('present', 'partial', 'absent', 'leave', 'field_duty', "
            "'holiday', 'weekly_off')",
            name="attendance_record_detail_valid_status",
        ),
        sa.CheckConstraint(
            "planned_minutes >= 0 AND break_minutes >= 0 "
            "AND early_arrival_minutes >= 0 AND early_departure_minutes >= 0 "
            "AND late_departure_minutes >= 0 AND regular_overtime_minutes >= 0 "
            "AND holiday_overtime_minutes >= 0 AND duplicate_event_count >= 0",
            name="attendance_record_detail_nonnegative_metrics",
        ),
        sa.ForeignKeyConstraint(
            ["attendance_record_id"],
            ["attendance_records.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("attendance_record_id"),
    )
    op.create_index(
        "ix_attendance_record_details_status",
        "attendance_record_details",
        ["day_status"],
    )

    op.create_table(
        "attendance_period_locks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("locked_by", sa.Uuid(), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reopened_by", sa.Uuid(), nullable=True),
        sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reopen_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "ends_on >= starts_on",
            name="attendance_period_lock_valid_dates",
        ),
        sa.CheckConstraint(
            "status IN ('locked', 'reopened')",
            name="attendance_period_lock_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["company_profiles.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["locked_by"],
            ["user_accounts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reopened_by"],
            ["user_accounts.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_attendance_period_locks_org_dates",
        "attendance_period_locks",
        ["organization_id", "starts_on", "ends_on", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_attendance_period_locks_org_dates",
        table_name="attendance_period_locks",
    )
    op.drop_table("attendance_period_locks")
    op.drop_index(
        "ix_attendance_record_details_status",
        table_name="attendance_record_details",
    )
    op.drop_table("attendance_record_details")
    op.drop_index(
        "ix_attendance_day_remarks_employee_date",
        table_name="attendance_day_remarks",
    )
    op.drop_table("attendance_day_remarks")
    op.drop_index(
        "ix_attendance_import_rows_session_valid",
        table_name="attendance_import_rows",
    )
    op.drop_table("attendance_import_rows")
    op.drop_index(
        "ix_manual_attendance_events_org_status",
        table_name="manual_attendance_events",
    )
    op.drop_index(
        "ix_manual_attendance_events_employee_time",
        table_name="manual_attendance_events",
    )
    op.drop_table("manual_attendance_events")
    op.drop_index(
        "ix_attendance_import_sessions_org_created",
        table_name="attendance_import_sessions",
    )
    op.drop_table("attendance_import_sessions")
    op.drop_table("attendance_policies")
