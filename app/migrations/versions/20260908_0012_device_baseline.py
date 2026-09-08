"""Add persistent device jobs, encrypted archives, and diagnostics.

Revision ID: 20260908_0012
Revises: 20260908_0011
Create Date: 2026-09-08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0012"
down_revision: str | None = "20260908_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "job_type IN ('immediate_pull', 'historical_pull', 'sync_users', "
            "'push_user', 'migrate_user', 'archive_user', 'restore_user')",
            name="device_job_valid_type",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="device_job_valid_status",
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
            name="device_job_valid_times",
        ),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["user_accounts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_device_jobs_status_created",
        "device_jobs",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_device_jobs_org_device",
        "device_jobs",
        ["organization_id", "device_id"],
        unique=False,
    )
    op.create_table(
        "device_identity_archives",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("external_user_id", sa.String(length=200), nullable=False),
        sa.Column("key_id", sa.String(length=120), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["user_accounts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_device_archives_org_device",
        "device_identity_archives",
        ["organization_id", "device_id"],
        unique=False,
    )
    op.create_table(
        "device_diagnostic_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("reachable", sa.Boolean(), nullable=False),
        sa.Column("firmware_version", sa.String(length=160), nullable=True),
        sa.Column("device_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message", sa.String(length=400), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["company_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_device_diagnostics_device_time",
        "device_diagnostic_snapshots",
        ["device_id", "observed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_device_diagnostics_device_time", table_name="device_diagnostic_snapshots"
    )
    op.drop_table("device_diagnostic_snapshots")
    op.drop_index("ix_device_archives_org_device", table_name="device_identity_archives")
    op.drop_table("device_identity_archives")
    op.drop_index("ix_device_jobs_org_device", table_name="device_jobs")
    op.drop_index("ix_device_jobs_status_created", table_name="device_jobs")
    op.drop_table("device_jobs")
