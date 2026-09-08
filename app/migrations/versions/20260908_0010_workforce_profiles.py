"""Add company report metadata and extended employee profiles.

Revision ID: 20260908_0010
Revises: 20260907_0009
Create Date: 2026-09-08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0010"
down_revision: str | None = "20260907_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_report_profiles",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("address", sa.String(length=300), nullable=True),
        sa.Column("contact_email", sa.String(length=254), nullable=True),
        sa.Column("contact_phone", sa.String(length=80), nullable=True),
        sa.Column("report_header", sa.String(length=240), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("organization_id"),
    )
    op.create_table(
        "employee_profiles",
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("attendance_id", sa.Integer(), nullable=True),
        sa.Column("hr_employee_number", sa.String(length=80), nullable=True),
        sa.Column("employment_type", sa.String(length=24), nullable=False),
        sa.Column("designation", sa.String(length=160), nullable=True),
        sa.Column("grade_level", sa.String(length=80), nullable=True),
        sa.Column("contact_email", sa.String(length=254), nullable=True),
        sa.Column("contact_phone", sa.String(length=80), nullable=True),
        sa.Column("payroll_reference", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "employment_type IN ('permanent', 'contract', 'temporary', 'intern', 'consultant')",
            name="employee_profile_valid_employment_type",
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("employee_id"),
        sa.UniqueConstraint(
            "organization_id", "attendance_id", name="uq_employee_profile_org_attendance_id"
        ),
        sa.UniqueConstraint(
            "organization_id", "hr_employee_number", name="uq_employee_profile_org_hr_number"
        ),
    )
    op.create_index(
        "ix_employee_profiles_org_employment_type",
        "employee_profiles",
        ["organization_id", "employment_type"],
        unique=False,
    )
    op.create_index(
        "ix_employee_profiles_org_attendance_id",
        "employee_profiles",
        ["organization_id", "attendance_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_employee_profiles_org_attendance_id", table_name="employee_profiles")
    op.drop_index("ix_employee_profiles_org_employment_type", table_name="employee_profiles")
    op.drop_table("employee_profiles")
    op.drop_table("company_report_profiles")
