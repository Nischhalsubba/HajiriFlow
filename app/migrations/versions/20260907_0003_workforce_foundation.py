"""Add organization, employee, and shift foundation.

Revision ID: 20260907_0003
Revises: 20260803_0002
Create Date: 2026-09-07
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_0003"
down_revision: str | None = "20260803_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("legal_name", sa.String(length=240), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name="company_profile_valid_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_company_profiles_status",
        "company_profiles",
        ["status"],
        unique=False,
    )

    op.create_table(
        "organization_nodes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("node_type", sa.String(length=24), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "node_type IN ('directorate', 'department', 'section', 'unit')",
            name="organization_node_valid_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name="organization_node_valid_status",
        ),
        sa.CheckConstraint(
            "parent_id IS NULL OR parent_id <> id",
            name="organization_node_not_own_parent",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["organization_nodes.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "code", name="uq_organization_node_code"
        ),
    )
    op.create_index(
        "ix_organization_nodes_org_parent",
        "organization_nodes",
        ["organization_id", "parent_id"],
        unique=False,
    )
    op.create_index(
        "ix_organization_nodes_org_type_status",
        "organization_nodes",
        ["organization_id", "node_type", "status"],
        unique=False,
    )

    op.create_table(
        "employees",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("employee_code", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("joined_on", sa.Date(), nullable=False),
        sa.Column("left_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'terminated')",
            name="employee_valid_status",
        ),
        sa.CheckConstraint(
            "left_on IS NULL OR left_on >= joined_on",
            name="employee_valid_dates",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "employee_code", name="uq_employee_org_code"
        ),
    )
    op.create_index(
        "ix_employees_org_status",
        "employees",
        ["organization_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_employees_org_name",
        "employees",
        ["organization_id", "display_name"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_user_accounts_employee_id",
        "user_accounts",
        "employees",
        ["employee_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "employee_organization_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("organization_node_id", sa.Uuid(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "ends_on IS NULL OR ends_on >= starts_on",
            name="employee_org_assignment_valid_dates",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["employees.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_node_id"], ["organization_nodes.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_employee_org_assignments_employee_dates",
        "employee_organization_assignments",
        ["employee_id", "starts_on", "ends_on"],
        unique=False,
    )
    op.create_index(
        "ix_employee_org_assignments_node_dates",
        "employee_organization_assignments",
        ["organization_node_id", "starts_on", "ends_on"],
        unique=False,
    )

    op.create_table(
        "shifts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("starts_at", sa.Time(), nullable=False),
        sa.Column("ends_at", sa.Time(), nullable=False),
        sa.Column("break_minutes", sa.Integer(), nullable=False),
        sa.Column("grace_minutes", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("break_minutes >= 0", name="shift_nonnegative_break"),
        sa.CheckConstraint("grace_minutes >= 0", name="shift_nonnegative_grace"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_shift_org_code"),
    )
    op.create_index(
        "ix_shifts_org_active",
        "shifts",
        ["organization_id", "active"],
        unique=False,
    )

    op.create_table(
        "shift_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("shift_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=True),
        sa.Column("organization_node_id", sa.Uuid(), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(employee_id IS NOT NULL AND organization_node_id IS NULL) OR "
            "(employee_id IS NULL AND organization_node_id IS NOT NULL)",
            name="shift_assignment_exactly_one_target",
        ),
        sa.CheckConstraint(
            "ends_on IS NULL OR ends_on >= starts_on",
            name="shift_assignment_valid_dates",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["employees.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_node_id"], ["organization_nodes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_shift_assignments_employee_dates",
        "shift_assignments",
        ["employee_id", "starts_on", "ends_on"],
        unique=False,
    )
    op.create_index(
        "ix_shift_assignments_node_dates",
        "shift_assignments",
        ["organization_node_id", "starts_on", "ends_on"],
        unique=False,
    )
    op.create_index(
        "ix_shift_assignments_shift_dates",
        "shift_assignments",
        ["shift_id", "starts_on", "ends_on"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_shift_assignments_shift_dates", table_name="shift_assignments")
    op.drop_index("ix_shift_assignments_node_dates", table_name="shift_assignments")
    op.drop_index("ix_shift_assignments_employee_dates", table_name="shift_assignments")
    op.drop_table("shift_assignments")
    op.drop_index("ix_shifts_org_active", table_name="shifts")
    op.drop_table("shifts")
    op.drop_index(
        "ix_employee_org_assignments_node_dates",
        table_name="employee_organization_assignments",
    )
    op.drop_index(
        "ix_employee_org_assignments_employee_dates",
        table_name="employee_organization_assignments",
    )
    op.drop_table("employee_organization_assignments")
    op.drop_constraint("fk_user_accounts_employee_id", "user_accounts", type_="foreignkey")
    op.drop_index("ix_employees_org_name", table_name="employees")
    op.drop_index("ix_employees_org_status", table_name="employees")
    op.drop_table("employees")
    op.drop_index("ix_organization_nodes_org_type_status", table_name="organization_nodes")
    op.drop_index("ix_organization_nodes_org_parent", table_name="organization_nodes")
    op.drop_table("organization_nodes")
    op.drop_index("ix_company_profiles_status", table_name="company_profiles")
    op.drop_table("company_profiles")
