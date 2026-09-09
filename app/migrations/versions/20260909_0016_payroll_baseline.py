"""Add payroll policy, generation review, and self-service baseline.

Revision ID: 20260909_0016
Revises: 20260909_0015
Create Date: 2026-09-09
"""
from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0016"
down_revision: str | None = "20260909_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fiscal_years",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("bs_start_year", sa.Integer(), nullable=False),
        sa.Column("bs_end_year", sa.Integer(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_by", sa.Uuid(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", sa.Uuid(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.Uuid(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("ends_on >= starts_on", name="fiscal_year_valid_dates"),
        sa.CheckConstraint(
            "status IN ('upcoming', 'active', 'closed', 'locked')",
            name="fiscal_year_valid_status",
        ),
        sa.CheckConstraint("bs_start_year >= 2000", name="fiscal_year_valid_bs_start"),
        sa.CheckConstraint(
            "bs_end_year >= bs_start_year",
            name="fiscal_year_valid_bs_end",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["activated_by"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["closed_by"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["locked_by"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_fiscal_year_org_code"),
    )
    op.create_index(
        "ix_fiscal_year_org_status",
        "fiscal_years",
        ["organization_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_fiscal_year_org_dates",
        "fiscal_years",
        ["organization_id", "starts_on", "ends_on"],
        unique=False,
    )

    op.create_table(
        "earning_heads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("calculation_type", sa.String(length=20), nullable=False),
        sa.Column("payment_frequency", sa.String(length=20), nullable=False),
        sa.Column("taxable", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "calculation_type IN ('fixed', 'percentage')",
            name="earning_head_valid_calculation_type",
        ),
        sa.CheckConstraint(
            "payment_frequency IN ('monthly', 'annual', 'one_time')",
            name="earning_head_valid_frequency",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_earning_head_org_code"),
    )
    op.create_index(
        "ix_earning_head_org_active",
        "earning_heads",
        ["organization_id", "active"],
        unique=False,
    )

    op.create_table(
        "deduction_types",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("calculation_type", sa.String(length=20), nullable=False),
        sa.Column("payment_frequency", sa.String(length=20), nullable=False),
        sa.Column("pretax", sa.Boolean(), nullable=False),
        sa.Column("enrollment_required", sa.Boolean(), nullable=False),
        sa.Column("cap_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "calculation_type IN ('fixed', 'percentage')",
            name="deduction_type_valid_calculation_type",
        ),
        sa.CheckConstraint(
            "payment_frequency IN ('monthly', 'annual', 'one_time')",
            name="deduction_type_valid_frequency",
        ),
        sa.CheckConstraint(
            "cap_amount IS NULL OR cap_amount >= 0",
            name="deduction_type_nonnegative_cap",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_deduction_type_org_code"),
    )
    op.create_index(
        "ix_deduction_type_org_active",
        "deduction_types",
        ["organization_id", "active"],
        unique=False,
    )

    op.create_table(
        "employee_compensation_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("base_salary", sa.Numeric(18, 2), nullable=False),
        sa.Column("tax_category", sa.String(length=60), nullable=False),
        sa.Column("overtime_eligible", sa.Boolean(), nullable=False),
        sa.Column("standard_monthly_minutes", sa.Integer(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("base_salary >= 0", name="comp_profile_nonnegative_salary"),
        sa.CheckConstraint(
            "standard_monthly_minutes > 0",
            name="comp_profile_positive_monthly_minutes",
        ),
        sa.CheckConstraint(
            "ends_on IS NULL OR ends_on >= starts_on",
            name="comp_profile_valid_dates",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_comp_profile_employee_dates",
        "employee_compensation_profiles",
        ["employee_id", "starts_on", "ends_on"],
        unique=False,
    )
    op.create_index(
        "ix_comp_profile_org_active",
        "employee_compensation_profiles",
        ["organization_id", "active"],
        unique=False,
    )

    op.create_table(
        "holiday_overtime_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=True),
        sa.Column("multiplier", sa.Numeric(8, 4), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "scope_type IN ('organization', 'employee')",
            name="holiday_ot_valid_scope",
        ),
        sa.CheckConstraint(
            "(scope_type = 'organization' AND employee_id IS NULL) OR "
            "(scope_type = 'employee' AND employee_id IS NOT NULL)",
            name="holiday_ot_scope_matches_employee",
        ),
        sa.CheckConstraint("multiplier >= 1", name="holiday_ot_valid_multiplier"),
        sa.CheckConstraint(
            "ends_on IS NULL OR ends_on >= starts_on",
            name="holiday_ot_valid_dates",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_holiday_ot_org_dates",
        "holiday_overtime_rules",
        ["organization_id", "starts_on", "ends_on"],
        unique=False,
    )
    op.create_index(
        "ix_holiday_ot_employee_dates",
        "holiday_overtime_rules",
        ["employee_id", "starts_on", "ends_on"],
        unique=False,
    )

    op.create_table(
        "employee_compensation_components",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("compensation_profile_id", sa.Uuid(), nullable=False),
        sa.Column("component_type", sa.String(length=20), nullable=False),
        sa.Column("earning_head_id", sa.Uuid(), nullable=True),
        sa.Column("deduction_type_id", sa.Uuid(), nullable=True),
        sa.Column("value", sa.Numeric(18, 4), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "component_type IN ('earning', 'deduction')",
            name="comp_component_valid_type",
        ),
        sa.CheckConstraint("value >= 0", name="comp_component_nonnegative_value"),
        sa.CheckConstraint(
            "(component_type = 'earning' AND earning_head_id IS NOT NULL "
            "AND deduction_type_id IS NULL) OR "
            "(component_type = 'deduction' AND deduction_type_id IS NOT NULL "
            "AND earning_head_id IS NULL)",
            name="comp_component_reference_matches_type",
        ),
        sa.ForeignKeyConstraint(
            ["compensation_profile_id"],
            ["employee_compensation_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["earning_head_id"], ["earning_heads.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["deduction_type_id"], ["deduction_types.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_comp_component_profile",
        "employee_compensation_components",
        ["compensation_profile_id"],
        unique=False,
    )

    op.create_table(
        "tax_slab_sets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("fiscal_year_id", sa.Uuid(), nullable=False),
        sa.Column("taxpayer_category", sa.String(length=60), nullable=False),
        sa.Column("version", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("standard_deduction", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_by", sa.Uuid(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'confirmed')",
            name="tax_slab_set_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["fiscal_year_id"], ["fiscal_years.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["confirmed_by"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "fiscal_year_id",
            "taxpayer_category",
            "version",
            name="uq_tax_slab_set_fy_category_version",
        ),
    )
    op.create_index(
        "ix_tax_slab_set_org_category_status",
        "tax_slab_sets",
        ["organization_id", "taxpayer_category", "status"],
        unique=False,
    )

    op.create_table(
        "tax_slabs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tax_slab_set_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("lower_bound", sa.Numeric(18, 2), nullable=False),
        sa.Column("upper_bound", sa.Numeric(18, 2), nullable=True),
        sa.Column("rate", sa.Numeric(8, 6), nullable=False),
        sa.CheckConstraint("lower_bound >= 0", name="tax_slab_nonnegative_lower"),
        sa.CheckConstraint(
            "upper_bound IS NULL OR upper_bound > lower_bound",
            name="tax_slab_valid_bounds",
        ),
        sa.CheckConstraint("rate >= 0 AND rate <= 1", name="tax_slab_valid_rate"),
        sa.ForeignKeyConstraint(
            ["tax_slab_set_id"], ["tax_slab_sets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tax_slab_set_id", "sequence", name="uq_tax_slab_set_sequence"),
    )
    op.create_index(
        "ix_tax_slab_set_bounds",
        "tax_slabs",
        ["tax_slab_set_id", "lower_bound"],
        unique=False,
    )

    op.create_table(
        "payroll_period_contexts",
        sa.Column("period_id", sa.Uuid(), nullable=False),
        sa.Column("fiscal_year_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["period_id"], ["payroll_periods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fiscal_year_id"], ["fiscal_years.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("period_id"),
    )

    op.create_table(
        "payroll_attendance_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("period_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attendance_snapshot", sa.JSON(), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="payroll_attendance_review_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["period_id"], ["payroll_periods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "period_id",
            "employee_id",
            name="uq_payroll_attendance_review_period_employee",
        ),
    )
    op.create_index(
        "ix_payroll_attendance_review_status",
        "payroll_attendance_reviews",
        ["period_id", "status"],
        unique=False,
    )

    op.create_table(
        "payroll_adjustments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("adjustment_type", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "adjustment_type IN ('earning', 'deduction')",
            name="payroll_adjustment_valid_type",
        ),
        sa.CheckConstraint("amount > 0", name="payroll_adjustment_positive_amount"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["payroll_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_payroll_adjustment_run_employee",
        "payroll_adjustments",
        ["run_id", "employee_id"],
        unique=False,
    )

    bind = op.get_bind()
    permission_code = "payroll.self.read"
    bind.execute(
        sa.text(
            "INSERT INTO permissions (id, code, description, created_at) "
            "VALUES (:id, :code, :description, CURRENT_TIMESTAMP) "
            "ON CONFLICT (code) DO NOTHING"
        ),
        {
            "id": str(uuid4()),
            "code": permission_code,
            "description": "View the signed-in employee's own posted payroll and payslips.",
        },
    )
    bind.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT roles.id, permissions.id FROM roles, permissions "
            "WHERE roles.code = 'employee' AND permissions.code = :permission_code "
            "ON CONFLICT DO NOTHING"
        ),
        {"permission_code": permission_code},
    )


def downgrade() -> None:
    bind = op.get_bind()
    permission_code = "payroll.self.read"
    bind.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE role_id IN "
            "(SELECT id FROM roles WHERE code = 'employee') AND permission_id IN "
            "(SELECT id FROM permissions WHERE code = :permission_code)"
        ),
        {"permission_code": permission_code},
    )
    bind.execute(
        sa.text("DELETE FROM permissions WHERE code = :permission_code"),
        {"permission_code": permission_code},
    )

    op.drop_index("ix_payroll_adjustment_run_employee", table_name="payroll_adjustments")
    op.drop_table("payroll_adjustments")
    op.drop_index(
        "ix_payroll_attendance_review_status",
        table_name="payroll_attendance_reviews",
    )
    op.drop_table("payroll_attendance_reviews")
    op.drop_table("payroll_period_contexts")
    op.drop_index("ix_tax_slab_set_bounds", table_name="tax_slabs")
    op.drop_table("tax_slabs")
    op.drop_index("ix_tax_slab_set_org_category_status", table_name="tax_slab_sets")
    op.drop_table("tax_slab_sets")
    op.drop_index("ix_comp_component_profile", table_name="employee_compensation_components")
    op.drop_table("employee_compensation_components")
    op.drop_index("ix_holiday_ot_employee_dates", table_name="holiday_overtime_rules")
    op.drop_index("ix_holiday_ot_org_dates", table_name="holiday_overtime_rules")
    op.drop_table("holiday_overtime_rules")
    op.drop_index("ix_comp_profile_org_active", table_name="employee_compensation_profiles")
    op.drop_index("ix_comp_profile_employee_dates", table_name="employee_compensation_profiles")
    op.drop_table("employee_compensation_profiles")
    op.drop_index("ix_deduction_type_org_active", table_name="deduction_types")
    op.drop_table("deduction_types")
    op.drop_index("ix_earning_head_org_active", table_name="earning_heads")
    op.drop_table("earning_heads")
    op.drop_index("ix_fiscal_year_org_dates", table_name="fiscal_years")
    op.drop_index("ix_fiscal_year_org_status", table_name="fiscal_years")
    op.drop_table("fiscal_years")
