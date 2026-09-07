"""Add shared calendar, leave, and field-duty foundation.

Revision ID: 20260907_0004
Revises: 20260907_0003
Create Date: 2026-09-07
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_0004"
down_revision: str | None = "20260907_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_calendar_settings",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("weekend_weekdays", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("organization_id"),
    )

    op.create_table(
        "holidays",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("holiday_date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("paid", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "category IN ('public', 'organization', 'optional')",
            name="holiday_valid_category",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'cancelled')",
            name="holiday_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "holiday_date",
            "name",
            name="uq_holiday_org_date_name",
        ),
    )
    op.create_index(
        "ix_holidays_org_date",
        "holidays",
        ["organization_id", "holiday_date"],
        unique=False,
    )

    op.create_table(
        "leave_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("paid", sa.Boolean(), nullable=False),
        sa.Column("half_day_allowed", sa.Boolean(), nullable=False),
        sa.Column("annual_entitlement", sa.Numeric(8, 2), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "annual_entitlement >= 0",
            name="leave_policy_nonnegative_entitlement",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "code", name="uq_leave_policy_org_code"
        ),
    )
    op.create_index(
        "ix_leave_policies_org_active",
        "leave_policies",
        ["organization_id", "active"],
        unique=False,
    )

    op.create_table(
        "leave_allocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("leave_policy_id", sa.Uuid(), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("allocated_days", sa.Numeric(8, 2), nullable=False),
        sa.Column("carried_days", sa.Numeric(8, 2), nullable=False),
        sa.Column("adjustment_days", sa.Numeric(8, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "period_year >= 2000", name="leave_allocation_valid_year"
        ),
        sa.CheckConstraint(
            "allocated_days >= 0",
            name="leave_allocation_nonnegative_allocated",
        ),
        sa.CheckConstraint(
            "carried_days >= 0", name="leave_allocation_nonnegative_carried"
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["employees.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["leave_policy_id"], ["leave_policies.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "employee_id",
            "leave_policy_id",
            "period_year",
            name="uq_leave_allocation_employee_policy_year",
        ),
    )
    op.create_index(
        "ix_leave_allocations_org_year",
        "leave_allocations",
        ["organization_id", "period_year"],
        unique=False,
    )

    op.create_table(
        "leave_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("leave_policy_id", sa.Uuid(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("day_part", sa.String(length=20), nullable=False),
        sa.Column("requested_days", sa.Numeric(8, 2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "end_date >= start_date", name="leave_request_valid_dates"
        ),
        sa.CheckConstraint(
            "day_part IN ('full', 'first_half', 'second_half')",
            name="leave_request_valid_day_part",
        ),
        sa.CheckConstraint(
            "requested_days > 0", name="leave_request_positive_days"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="leave_request_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["user_accounts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["employees.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["leave_policy_id"], ["leave_policies.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["user_accounts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_leave_requests_employee_dates",
        "leave_requests",
        ["employee_id", "start_date", "end_date"],
        unique=False,
    )
    op.create_index(
        "ix_leave_requests_org_status",
        "leave_requests",
        ["organization_id", "status"],
        unique=False,
    )

    op.create_table(
        "field_duty_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("paid", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "end_date >= start_date", name="field_duty_valid_dates"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="field_duty_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["user_accounts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["employees.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["user_accounts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_field_duty_employee_dates",
        "field_duty_requests",
        ["employee_id", "start_date", "end_date"],
        unique=False,
    )
    op.create_index(
        "ix_field_duty_org_status",
        "field_duty_requests",
        ["organization_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_field_duty_org_status", table_name="field_duty_requests")
    op.drop_index("ix_field_duty_employee_dates", table_name="field_duty_requests")
    op.drop_table("field_duty_requests")
    op.drop_index("ix_leave_requests_org_status", table_name="leave_requests")
    op.drop_index("ix_leave_requests_employee_dates", table_name="leave_requests")
    op.drop_table("leave_requests")
    op.drop_index("ix_leave_allocations_org_year", table_name="leave_allocations")
    op.drop_table("leave_allocations")
    op.drop_index("ix_leave_policies_org_active", table_name="leave_policies")
    op.drop_table("leave_policies")
    op.drop_index("ix_holidays_org_date", table_name="holidays")
    op.drop_table("holidays")
    op.drop_table("organization_calendar_settings")
