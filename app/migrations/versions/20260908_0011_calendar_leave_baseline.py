"""Complete calendar and leave baseline detail records.

Revision ID: 20260908_0011
Revises: 20260908_0010
Create Date: 2026-09-08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0011"
down_revision: str | None = "20260908_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "leave_policy_rules",
        sa.Column("leave_policy_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("carry_forward_allowed", sa.Boolean(), nullable=False),
        sa.Column("carry_forward_cap", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("color_hex", sa.String(length=7), nullable=False),
        sa.Column("eligibility_employment_types", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "carry_forward_cap IS NULL OR carry_forward_cap >= 0",
            name="leave_policy_rule_nonnegative_carry_cap",
        ),
        sa.ForeignKeyConstraint(
            ["leave_policy_id"], ["leave_policies.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("leave_policy_id"),
    )
    op.create_table(
        "leave_allocation_details",
        sa.Column("leave_allocation_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("opening_days", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("earned_days", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "opening_days >= 0", name="leave_allocation_detail_opening_nonnegative"
        ),
        sa.CheckConstraint(
            "earned_days >= 0", name="leave_allocation_detail_earned_nonnegative"
        ),
        sa.CheckConstraint(
            "source IN ('manual', 'annual')",
            name="leave_allocation_detail_valid_source",
        ),
        sa.ForeignKeyConstraint(
            ["leave_allocation_id"], ["leave_allocations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("leave_allocation_id"),
    )
    op.create_table(
        "field_duty_details",
        sa.Column("field_duty_request_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("location", sa.String(length=240), nullable=True),
        sa.Column("evidence_reference", sa.String(length=400), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["field_duty_request_id"], ["field_duty_requests.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("field_duty_request_id"),
    )


def downgrade() -> None:
    op.drop_table("field_duty_details")
    op.drop_table("leave_allocation_details")
    op.drop_table("leave_policy_rules")
