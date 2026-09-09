"""Add queued device operations and runtime configuration.

Revision ID: 20260909_0012
Revises: 20260908_0011
Create Date: 2026-09-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0012"
down_revision: str | None = "20260908_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device_runtime_configurations",
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("site", sa.String(length=160), nullable=True),
        sa.Column("protocol_preference", sa.String(length=40), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("last_successful_pull_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_diagnostics_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("timeout_seconds >= 1", name="device_runtime_positive_timeout"),
        sa.CheckConstraint("timeout_seconds <= 120", name="device_runtime_bounded_timeout"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("device_id"),
    )
    op.create_table(
        "device_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("operation_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_data", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "operation_type IN ('diagnostics', 'immediate_pull', 'historical_pull')",
            name="device_operation_valid_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'skipped')",
            name="device_operation_valid_status",
        ),
        sa.CheckConstraint(
            "window_end IS NULL OR window_start IS NOT NULL",
            name="device_operation_window_start_required",
        ),
        sa.CheckConstraint(
            "window_end IS NULL OR window_end >= window_start",
            name="device_operation_valid_window",
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["user_accounts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_device_operations_device_created",
        "device_operations",
        ["device_id", "created_at"],
    )
    op.create_index(
        "ix_device_operations_status_created",
        "device_operations",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_device_operations_org_status",
        "device_operations",
        ["organization_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_device_operations_org_status", table_name="device_operations")
    op.drop_index("ix_device_operations_status_created", table_name="device_operations")
    op.drop_index("ix_device_operations_device_created", table_name="device_operations")
    op.drop_table("device_operations")
    op.drop_table("device_runtime_configurations")
